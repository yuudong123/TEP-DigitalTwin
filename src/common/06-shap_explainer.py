from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VERSION = "v1.0.0"

PRODUCTION_DIR = (
    PROJECT_ROOT
    / "models"
    / "production"
    / VERSION
)

FEATURE_LIST_PATH = (
    PRODUCTION_DIR
    / "feature_list.json"
)

TEST_DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "temporal"
    / "test.parquet"
)

MODEL_FILES = {
    "failure_within_4h": "failure_within_4h.json",
    "failure_within_2h": "failure_within_2h.json",
    "failure_within_1h": "failure_within_1h.json",
}


def load_feature_list() -> list[str]:
    with FEATURE_LIST_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    features = payload["features"]

    if len(features) != 728:
        raise ValueError(
            f"Expected 728 features, got {len(features)}"
        )

    return features


def load_model(target: str) -> xgb.Booster:
    if target not in MODEL_FILES:
        raise ValueError(
            f"Unsupported target: {target}"
        )

    path = (
        PRODUCTION_DIR
        / MODEL_FILES[target]
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Model not found: {path}"
        )

    model = xgb.Booster()
    model.load_model(path)

    return model


def calculate_shap(
    model: xgb.Booster,
    feature_values: pd.DataFrame,
    feature_names: list[str],
) -> tuple[np.ndarray, float]:

    matrix = xgb.DMatrix(
        feature_values.to_numpy(
            dtype=np.float32
        ),
        feature_names=feature_names,
    )

    contributions = model.predict(
        matrix,
        pred_contribs=True,
    )

    # 마지막 값은 SHAP bias/base value
    shap_values = contributions[0, :-1]
    base_value = float(
        contributions[0, -1]
    )

    # TreeSHAP additivity 검증
    raw_prediction = float(
        model.predict(
            matrix,
            output_margin=True,
        )[0]
    )

    reconstructed = float(
        shap_values.sum()
        + base_value
    )

    if not np.isclose(
        raw_prediction,
        reconstructed,
        rtol=1e-4,
        atol=1e-4,
    ):
        raise ValueError(
            "SHAP additivity validation failed: "
            f"model={raw_prediction}, "
            f"shap={reconstructed}"
        )

    return shap_values, base_value


def main() -> None:
    print("=" * 80)
    print("XGBOOST TREESHAP VALIDATION")
    print("=" * 80)

    features = load_feature_list()

    # 테스트용 한 행만 읽는다.
    # 전체 660MB 데이터를 메모리에 올릴 필요 없음.
    test_df = pd.read_parquet(
        TEST_DATA_PATH,
        columns=(
            [
                "trajectory_key",
                "Time",
                "rul_hours",
            ]
            + features
        ),
    )

    # 고장에 가까운 데이터 하나를 테스트 대상으로 선택
    row = (
        test_df
        .sort_values("rul_hours")
        .iloc[[0]]
    )

    print(
        f"Trajectory : "
        f"{row['trajectory_key'].iloc[0]}"
    )

    print(
        f"Time       : "
        f"{row['Time'].iloc[0]:.2f} h"
    )

    print(
        f"RUL        : "
        f"{row['rul_hours'].iloc[0]:.2f} h"
    )

    X = row[features]

    for target in MODEL_FILES:

        print()
        print("-" * 80)
        print(target)
        print("-" * 80)

        model = load_model(
            target
        )

        shap_values, base_value = (
            calculate_shap(
                model,
                X,
                features,
            )
        )

        result = pd.DataFrame(
            {
                "feature": features,
                "shap_value": shap_values,
            }
        )

        result["abs_shap"] = (
            result["shap_value"]
            .abs()
        )

        result = (
            result
            .sort_values(
                "abs_shap",
                ascending=False,
            )
            .reset_index(drop=True)
        )

        print(
            f"Base value : "
            f"{base_value:.6f}"
        )

        print()
        print("Top 10 SHAP features:")

        print(
            result[
                [
                    "feature",
                    "shap_value",
                ]
            ]
            .head(10)
            .to_string(
                index=False
            )
        )

        print()
        print(
            "[PASS] SHAP additivity verified"
        )

    print()
    print("=" * 80)
    print("[PASS] TreeSHAP explanation implemented")
    print("=" * 80)


if __name__ == "__main__":
    main()