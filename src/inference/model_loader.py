"""Production XGBoost 모델 4개로 한 시점의 예측 결과를 만든다.

입력: temporal_features.py가 만든 728개 Feature
처리: RUL 1개와 4·2·1시간 고장 위험도 3개를 예측하고 상태를 판정
출력: RUL, 위험도, 상태, SHAP 위험요인이 포함된 Prediction 메시지
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from .prediction_schema import RISK_TARGETS, validate_prediction


# 이 파일들이 models/production/v1.0.0 폴더에 있어야 한다.
MODEL_FILES = {
    "rul_hours": "rul_hours.json",
    "failure_within_4h": "failure_within_4h.json",
    "failure_within_2h": "failure_within_2h.json",
    "failure_within_1h": "failure_within_1h.json",
}


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _threshold(payload: dict, target: str) -> float:
    value = payload[target]
    if isinstance(value, dict):
        value = value["threshold"]
    return float(value)


def determine_status(scores: dict[str, float], thresholds: dict[str, float]) -> tuple[str, str]:
    """가장 긴급한 위험부터 확인해 최종 화면 상태를 결정한다."""

    # 1시간 위험이 가장 급하므로 4시간보다 먼저 검사한다.
    if scores["failure_within_1h"] >= thresholds["failure_within_1h"]:
        return "CRITICAL", "failure_within_1h"
    if scores["failure_within_2h"] >= thresholds["failure_within_2h"]:
        return "WARNING", "failure_within_2h"
    if scores["failure_within_4h"] >= thresholds["failure_within_4h"]:
        return "CAUTION", "failure_within_4h"
    return "NORMAL", "failure_within_4h"


def _parse_window(value: object) -> int | None:
    if value is None or pd.isna(value) or str(value).lower() == "current":
        return None
    match = re.search(r"(5|15|30|60)", str(value))
    return int(match.group(1)) if match else None


class ProductionPredictor:
    def __init__(self, production_dir: Path) -> None:
        """서비스 시작 시 Feature 정보·임계값·모델 4개를 한 번만 불러온다."""
        self.production_dir = production_dir
        feature_payload = _load_json(production_dir / "feature_list.json")
        self.features = list(feature_payload["features"])
        if len(self.features) != 728:
            raise ValueError(f"모델 Feature는 728개여야 합니다: {len(self.features)}")

        self.metadata = _load_json(production_dir / "metadata.json")
        threshold_payload = _load_json(production_dir / "thresholds.json")
        self.thresholds = {
            target: _threshold(threshold_payload, target) for target in RISK_TARGETS
        }
        # 매 메시지마다 모델 파일을 다시 읽지 않도록 메모리에 보관한다.
        self.models: dict[str, xgb.Booster] = {}
        for target, filename in MODEL_FILES.items():
            path = production_dir / filename
            if not path.exists():
                raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다: {path}")
            model = xgb.Booster()
            model.load_model(path)
            self.models[target] = model

        schema = pd.read_csv(production_dir / "feature_schema.csv")
        self.feature_metadata = {
            str(row["feature"]): {
                "source_feature": str(row["source_feature"]),
                "transform": str(row["transform"]),
                "window_minutes": _parse_window(row.get("window")),
            }
            for _, row in schema.iterrows()
        }

    def _top_risk_factors(self, target: str, matrix: xgb.DMatrix) -> list[dict]:
        """현재 위험도를 높인 SHAP Feature 중 영향력이 큰 5개를 반환한다."""
        contributions = self.models[target].predict(matrix, pred_contribs=True)[0]
        rows = []
        for feature, shap_value in zip(self.features, contributions[:-1]):
            value = float(shap_value)
            # 음수 SHAP은 위험도를 낮추는 요인이므로 알림 원인 목록에서 제외한다.
            if value <= 0:
                continue
            meta = self.feature_metadata[feature]
            rows.append({
                "feature": feature,
                "source_feature": meta["source_feature"],
                "transform": meta["transform"],
                "window_minutes": meta["window_minutes"],
                "shap_value": value,
            })
        rows.sort(key=lambda item: item["shap_value"], reverse=True)
        result = []
        for rank, row in enumerate(rows[:5], start=1):
            result.append({"rank": rank, **row})
        return result

    def predict(self, features: pd.DataFrame, trajectory_key: str, timestamp_hours: float) -> dict:
        """현재 시점의 728개 Feature로 최종 Prediction 메시지를 만든다."""

        # 값이 같아도 열 순서가 다르면 모델 입력이 달라지므로 반드시 검사한다.
        if list(features.columns) != self.features:
            raise ValueError("실시간 Feature 순서가 feature_list.json과 다릅니다.")
        matrix = xgb.DMatrix(features, feature_names=self.features)
        # RUL은 물리적으로 음수가 될 수 없어서 화면에 표시할 값은 0 이상으로 제한한다.
        rul = max(0.0, float(self.models["rul_hours"].predict(matrix)[0]))
        scores = {
            target: float(self.models[target].predict(matrix)[0]) for target in RISK_TARGETS
        }
        status, explanation_target = determine_status(scores, self.thresholds)
        result = {
            "schema_version": "1.0",
            "model_version": str(self.metadata.get("version", "v1.0.0")),
            "trajectory_key": trajectory_key,
            "timestamp_hours": float(timestamp_hours),
            "rul": {"hours": rul},
            "risk": {
                target: {
                    "score": scores[target],
                    "threshold": self.thresholds[target],
                    "alert": bool(scores[target] >= self.thresholds[target]),
                }
                for target in RISK_TARGETS
            },
            "status": status,
            "explanation_model": explanation_target,
            "top_risk_factors": self._top_risk_factors(explanation_target, matrix),
        }
        validate_prediction(result)
        return result
