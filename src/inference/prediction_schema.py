"""실시간 추론 결과 메시지의 형식을 검사한다.

입력: model_loader.py가 만든 Prediction 딕셔너리
처리: 필수 필드, 상태값, 숫자, boolean 형식 확인
출력: 정상이면 그대로 통과하고 문제가 있으면 Kafka 전송 전에 오류 발생
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


STATUSES = {"NORMAL", "CAUTION", "WARNING", "CRITICAL"}
RISK_TARGETS = (
    "failure_within_4h",
    "failure_within_2h",
    "failure_within_1h",
)


def validate_prediction(message: dict[str, Any]) -> None:
    """웹/API가 안전하게 사용할 수 있는 Prediction 메시지인지 확인한다."""

    # 화면과 API가 반드시 필요로 하는 최상위 필드가 모두 있는지 확인한다.
    required = {
        "schema_version", "model_version", "trajectory_key",
        "timestamp_hours", "rul", "risk", "status",
        "explanation_model", "top_risk_factors",
    }
    missing = sorted(required - message.keys())
    if missing:
        raise ValueError(f"Prediction 필수 필드 누락: {missing}")
    if message["status"] not in STATUSES:
        raise ValueError(f"잘못된 status: {message['status']}")
    if message["explanation_model"] not in RISK_TARGETS:
        raise ValueError("잘못된 explanation_model입니다.")
    if not isinstance(message["trajectory_key"], str) or not message["trajectory_key"]:
        raise ValueError("trajectory_key는 비어 있지 않은 문자열이어야 합니다.")
    if not isinstance(message["rul"], Mapping) or "hours" not in message["rul"]:
        raise ValueError("rul.hours가 필요합니다.")
    if not isinstance(message["risk"], Mapping):
        raise ValueError("risk는 객체여야 합니다.")

    # JSON에 NaN이나 무한대가 들어가면 다른 서비스에서 처리할 수 없으므로 막는다.
    numbers = [message["timestamp_hours"], message["rul"]["hours"]]
    for target in RISK_TARGETS:
        if target not in message["risk"] or not isinstance(message["risk"][target], Mapping):
            raise ValueError(f"risk.{target} 객체가 필요합니다.")
        item = message["risk"][target]
        missing_risk_fields = {"score", "threshold", "alert"} - item.keys()
        if missing_risk_fields:
            raise ValueError(f"risk.{target} 필드 누락: {sorted(missing_risk_fields)}")
        numbers.extend([item["score"], item["threshold"]])
        if not isinstance(item["alert"], bool):
            raise ValueError(f"{target}.alert는 boolean이어야 합니다.")
        if not 0.0 <= float(item["score"]) <= 1.0:
            raise ValueError(f"{target}.score는 0과 1 사이여야 합니다.")
        if not 0.0 <= float(item["threshold"]) <= 1.0:
            raise ValueError(f"{target}.threshold는 0과 1 사이여야 합니다.")
    if not all(math.isfinite(float(value)) for value in numbers):
        raise ValueError("Prediction에 NaN 또는 무한대가 있습니다.")

    factors = message["top_risk_factors"]
    if not isinstance(factors, list) or len(factors) > 5:
        raise ValueError("top_risk_factors는 최대 5개의 목록이어야 합니다.")
    factor_fields = {
        "rank", "feature", "source_feature", "transform",
        "window_minutes", "shap_value",
    }
    for expected_rank, factor in enumerate(factors, start=1):
        if not isinstance(factor, Mapping):
            raise ValueError("각 위험요인은 객체여야 합니다.")
        missing_factor_fields = factor_fields - factor.keys()
        if missing_factor_fields:
            raise ValueError(f"위험요인 필드 누락: {sorted(missing_factor_fields)}")
        if factor["rank"] != expected_rank:
            raise ValueError("위험요인 rank가 1부터 순서대로 이어져야 합니다.")
        if not math.isfinite(float(factor["shap_value"])):
            raise ValueError("위험요인 shap_value는 유한한 숫자여야 합니다.")
