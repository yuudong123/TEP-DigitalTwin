"""새 실시간 계산식이 학습 당시 계산식과 같은지 확인하는 검증 파일.

이 파일은 실제 서비스를 운영하는 파일이 아니다. 코드를 설치한 뒤 한 번 실행해
728개 값이 학습 데이터 생성 방식과 일치하는지 확인하는 안전 검사다.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .temporal_features import base_features_from_feature_list, build_latest_features


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_offline_module():
    """기존 src/data/05-build_temporal_features.py를 비교 기준으로 불러온다."""
    path = PROJECT_ROOT / "src" / "data" / "05-build_temporal_features.py"
    spec = importlib.util.spec_from_file_location("offline_temporal", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"오프라인 Feature 코드를 불러올 수 없습니다: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    """선택한 trajectory의 한 시점에서 두 계산 결과를 비교한다."""
    parser = argparse.ArgumentParser(description="오프라인·실시간 Temporal Feature 비교")
    parser.add_argument("--case", default="case1")
    parser.add_argument("--id", type=int, default=1, dest="trajectory_id")
    parser.add_argument("--row", type=int, default=20, help="비교할 0-based 행 번호(20 이상)")
    args = parser.parse_args()

    model_dir = PROJECT_ROOT / "models" / "production" / "v1.0.0"
    feature_payload = json.loads((model_dir / "feature_list.json").read_text(encoding="utf-8"))
    ordered_features = feature_payload["features"]
    base_features = base_features_from_feature_list(ordered_features)
    source = pd.read_csv(PROJECT_ROOT / "data" / "raw" / f"{args.case}.csv")
    trajectory = source[source["Id"] == args.trajectory_id].sort_values("Time").reset_index(drop=True)
    if args.row < 20 or args.row >= len(trajectory):
        raise ValueError("--row는 20 이상이고 trajectory 행 개수보다 작아야 합니다.")

    # 오프라인 함수는 학습용 정답 열까지 요구하므로 비교 실행용 0을 채운다.
    trajectory = trajectory.copy()
    trajectory["case"] = args.case
    trajectory["trajectory_key"] = f"{args.case}::{args.trajectory_id}"
    for column in ["rul_hours", "rul_fraction", "failure_within_4h", "failure_within_2h", "failure_within_1h"]:
        trajectory[column] = 0

    # 같은 21개 행으로 기존 함수 결과(expected)와 새 함수 결과(actual)를 만든다.
    offline_module = _load_offline_module()
    offline = offline_module.build_features(trajectory.iloc[: args.row + 1], base_features)
    expected = offline.iloc[-1][ordered_features].to_numpy(dtype=np.float32)
    rows = trajectory.iloc[args.row - 20 : args.row + 1][base_features].to_dict("records")
    actual = build_latest_features(rows, base_features, ordered_features).iloc[0].to_numpy(dtype=np.float32)
    # 부동소수점 계산에는 극히 작은 오차가 생길 수 있어 allclose로 비교한다.
    difference = np.abs(expected - actual)
    print(f"비교 Feature: {len(actual)}개")
    print(f"최대 절대 오차: {float(difference.max()):.10f}")
    if not np.allclose(expected, actual, rtol=1e-5, atol=1e-5):
        raise ValueError("오프라인·실시간 Feature가 일치하지 않습니다.")
    print("최종 결과: 정상")


if __name__ == "__main__":
    main()
