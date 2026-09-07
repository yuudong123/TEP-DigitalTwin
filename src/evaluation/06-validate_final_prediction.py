from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import xgboost as xgb


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VERSION = "v1.0.0"

PRODUCTION_DIR = (
    PROJECT_ROOT
    / "models"
    / "production"
    / VERSION
)

TEST_DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "temporal"
    / "test.parquet"
)

FEATURE_LIST_PATH = (
    PRODUCTION_DIR
    / "feature_list.json"
)

FEATURE_SCHEMA_PATH = (
    PRODUCTION_DIR
    / "feature_schema.csv"
)

THRESHOLD_PATH = (
    PRODUCTION_DIR
    / "thresholds.json"
)

METADATA_PATH = (
    PRODUCTION_DIR
    / "metadata.json"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "06-final-model"
    / "sample_prediction.json"
)

MODEL_FILES = {
    "rul_hours":
        "rul_hours.json",

    "failure_within_4h":
        "failure_within_4h.json",

    "failure_within_2h":
        "failure_within_2h.json",

    "failure_within_1h":
        "failure_within_1h.json",
}


def load_json(
    path: Path,
) -> dict:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def load_model(
    filename: str,
) -> xgb.Booster:
    path = (
        PRODUCTION_DIR
        / filename
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Model not found: {path}"
        )

    model = xgb.Booster()
    model.load_model(path)

    return model


def load_sample(
    features: list[str],
) -> pd.DataFrame:
    """
    test.parquet 전체를 읽지 않고
    마지막 row group의 마지막 행 하나만 사용.
    """

    parquet_file = pq.ParquetFile(
        TEST_DATA_PATH
    )

    columns = [
        "trajectory_key",
        "Time",
        "rul_hours",
        *features,
    ]

    table = parquet_file.read_row_group(
        parquet_file.num_row_groups - 1,
        columns=columns,
    )

    df = table.to_pandas()

    if df.empty:
        raise ValueError(
            "No sample row found"
        )

    return df.tail(1).copy()


def get_threshold(
    thresholds: dict,
    target: str,
) -> float:
    """
    thresholds.json의 구조가
    {target: number}
    또는
    {target: {threshold: number}}
    둘 중 어느 형태여도 처리.
    """

    value = thresholds[target]

    if isinstance(value, dict):
        if "threshold" not in value:
            raise KeyError(
                f"No threshold value for {target}"
            )

        value = value["threshold"]

    return float(value)


def predict_score(
    model: xgb.Booster,
    matrix: xgb.DMatrix,
) -> float:
    return float(
        model.predict(
            matrix
        )[0]
    )


def determine_status(
    risk_4h: float,
    risk_2h: float,
    risk_1h: float,
    threshold_4h: float,
    threshold_2h: float,
    threshold_1h: float,
) -> tuple[str, str]:

    if risk_1h >= threshold_1h:
        return (
            "CRITICAL",
            "failure_within_1h",
        )

    if risk_2h >= threshold_2h:
        return (
            "WARNING",
            "failure_within_2h",
        )

    if risk_4h >= threshold_4h:
        return (
            "CAUTION",
            "failure_within_4h",
        )

    return (
        "NORMAL",
        "failure_within_4h",
    )


def parse_feature_name(
    feature: str,
) -> tuple[str, str, int | None]:
    """
    Feature schema에 설명용 필드가 없을 경우를 위한 fallback.

    이름에서 가능한 범위까지만 추출한다.
    정확한 명명 규칙을 모르는 경우에도 원본 feature 문자열은 보존한다.
    """

    lowered = feature.lower()

    transform_candidates = [
        "mean",
        "std",
        "delta",
        "rate",
        "slope",
        "max",
        "min",
    ]

    transform = "current"

    for candidate in transform_candidates:
        if candidate in lowered:
            transform = candidate
            break

    match = re.search(
        r"(5|15|30|60)\s*m",
        lowered,
    )

    if match:
        window_minutes = int(
            match.group(1)
        )
    else:
        window_minutes = None

    source_feature = feature

    separators = [
        "__",
        "_mean",
        "_std",
        "_delta",
        "_rate",
        "_slope",
        "_max",
        "_min",
    ]

    for separator in separators:
        if separator in source_feature:
            source_feature = (
                source_feature
                .split(separator)[0]
            )
            break

    return (
        source_feature,
        transform,
        window_minutes,
    )


def build_feature_metadata(
    features: list[str],
) -> dict[str, dict]:
    """
    feature_schema.csv에 설명 가능한 열이 있으면 사용하고,
    없으면 feature 이름으로 fallback.
    """

    result = {}

    if FEATURE_SCHEMA_PATH.exists():
        schema = pd.read_csv(
            FEATURE_SCHEMA_PATH
        )

        if "feature" in schema.columns:
            for _, row in schema.iterrows():
                feature = str(
                    row["feature"]
                )

                source_feature = (
                    row.get(
                        "source_feature",
                        None,
                    )
                )

                transform = (
                    row.get(
                        "transform",
                        None,
                    )
                )

                window = (
                    row.get(
                        "window_minutes",
                        None,
                    )
                )

                parsed = parse_feature_name(
                    feature
                )

                if (
                    source_feature is None
                    or pd.isna(source_feature)
                ):
                    source_feature = parsed[0]

                if (
                    transform is None
                    or pd.isna(transform)
                ):
                    transform = parsed[1]

                if (
                    window is None
                    or pd.isna(window)
                ):
                    window = parsed[2]

                if pd.isna(window):
                    window = None

                if window is not None:
                    try:
                        window = int(
                            window
                        )
                    except Exception:
                        window = None

                result[feature] = {
                    "source_feature":
                        str(source_feature),

                    "transform":
                        str(transform),

                    "window_minutes":
                        window,
                }

    for feature in features:
        if feature not in result:
            parsed = parse_feature_name(
                feature
            )

            result[feature] = {
                "source_feature":
                    parsed[0],

                "transform":
                    parsed[1],

                "window_minutes":
                    parsed[2],
            }

    return result


def calculate_top_risk_factors(
    model: xgb.Booster,
    matrix: xgb.DMatrix,
    features: list[str],
    feature_metadata: dict[str, dict],
    top_k: int = 5,
) -> list[dict]:

    contributions = model.predict(
        matrix,
        pred_contribs=True,
    )

    shap_values = (
        contributions[0, :-1]
    )

    base_value = float(
        contributions[0, -1]
    )

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
            "SHAP additivity validation failed"
        )

    rows = []

    for feature, shap_value in zip(
        features,
        shap_values,
    ):
        shap_value = float(
            shap_value
        )

        # 위험도를 증가시키는 Feature만 주요 위험요인으로 사용
        if shap_value <= 0:
            continue

        metadata = (
            feature_metadata[feature]
        )

        rows.append(
            {
                "feature": feature,

                "source_feature":
                    metadata[
                        "source_feature"
                    ],

                "transform":
                    metadata[
                        "transform"
                    ],

                "window_minutes":
                    metadata[
                        "window_minutes"
                    ],

                "shap_value":
                    shap_value,
            }
        )

    rows.sort(
        key=lambda x: x["shap_value"],
        reverse=True,
    )

    top_rows = rows[:top_k]

    for index, row in enumerate(
        top_rows,
        start=1,
    ):
        row["rank"] = index

    # rank를 첫 번째 필드처럼 보기 좋게 정리
    formatted = []

    for row in top_rows:
        formatted.append(
            {
                "rank":
                    row["rank"],

                "feature":
                    row["feature"],

                "source_feature":
                    row["source_feature"],

                "transform":
                    row["transform"],

                "window_minutes":
                    row["window_minutes"],

                "shap_value":
                    row["shap_value"],
            }
        )

    return formatted


def main() -> None:
    print("=" * 80)
    print("FINAL PRODUCTION PREDICTION VALIDATION")
    print("=" * 80)

    feature_payload = load_json(
        FEATURE_LIST_PATH
    )

    features = (
        feature_payload[
            "features"
        ]
    )

    if len(features) != 728:
        raise ValueError(
            f"Expected 728 features, got {len(features)}"
        )

    thresholds = load_json(
        THRESHOLD_PATH
    )

    metadata = load_json(
        METADATA_PATH
    )

    feature_metadata = (
        build_feature_metadata(
            features
        )
    )

    row = load_sample(
        features
    )

    X = row[features]

    matrix = xgb.DMatrix(
        X,
        feature_names=features,
    )

    models = {
        target: load_model(
            filename
        )
        for target, filename
        in MODEL_FILES.items()
    }

    # --------------------------------------------------------
    # RUL
    # --------------------------------------------------------

    rul_prediction = (
        predict_score(
            models["rul_hours"],
            matrix,
        )
    )

    # RUL은 물리적으로 음수가 될 수 없으므로
    # 표시값만 0 이상으로 제한
    rul_prediction = max(
        0.0,
        rul_prediction,
    )

    # --------------------------------------------------------
    # Risk scores
    # --------------------------------------------------------

    risk_4h = predict_score(
        models[
            "failure_within_4h"
        ],
        matrix,
    )

    risk_2h = predict_score(
        models[
            "failure_within_2h"
        ],
        matrix,
    )

    risk_1h = predict_score(
        models[
            "failure_within_1h"
        ],
        matrix,
    )

    threshold_4h = get_threshold(
        thresholds,
        "failure_within_4h",
    )

    threshold_2h = get_threshold(
        thresholds,
        "failure_within_2h",
    )

    threshold_1h = get_threshold(
        thresholds,
        "failure_within_1h",
    )

    status, explanation_target = (
        determine_status(
            risk_4h,
            risk_2h,
            risk_1h,
            threshold_4h,
            threshold_2h,
            threshold_1h,
        )
    )

    # --------------------------------------------------------
    # SHAP explanation
    # --------------------------------------------------------

    risk_factors = (
        calculate_top_risk_factors(
            models[
                explanation_target
            ],
            matrix,
            features,
            feature_metadata,
            top_k=5,
        )
    )

    # --------------------------------------------------------
    # Final prediction result
    # --------------------------------------------------------

    result = {
        "schema_version": "1.0",

        "model_version": (
            metadata.get(
                "version",
                VERSION,
            )
        ),

        "trajectory_key": str(
            row[
                "trajectory_key"
            ].iloc[0]
        ),

        "timestamp_hours": float(
            row["Time"].iloc[0]
        ),

        "rul": {
            "hours":
                rul_prediction,
        },

        "risk": {
            "failure_within_4h": {
                "score":
                    risk_4h,

                "threshold":
                    threshold_4h,

                "alert":
                    bool(
                        risk_4h
                        >= threshold_4h
                    ),
            },

            "failure_within_2h": {
                "score":
                    risk_2h,

                "threshold":
                    threshold_2h,

                "alert":
                    bool(
                        risk_2h
                        >= threshold_2h
                    ),
            },

            "failure_within_1h": {
                "score":
                    risk_1h,

                "threshold":
                    threshold_1h,

                "alert":
                    bool(
                        risk_1h
                        >= threshold_1h
                    ),
            },
        },

        "status":
            status,

        "explanation_model":
            explanation_target,

        "top_risk_factors":
            risk_factors,
    }

    # --------------------------------------------------------
    # Required-field validation
    # --------------------------------------------------------

    required_keys = [
        "model_version",
        "rul",
        "risk",
        "status",
        "top_risk_factors",
    ]

    for key in required_keys:
        if key not in result:
            raise ValueError(
                f"Missing output field: {key}"
            )

    if status not in {
        "NORMAL",
        "CAUTION",
        "WARNING",
        "CRITICAL",
    }:
        raise ValueError(
            f"Invalid status: {status}"
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )

    print()
    print("-" * 80)

    print(
        f"True RUL      : "
        f"{float(row['rul_hours'].iloc[0]):.4f} h"
    )

    print(
        f"Predicted RUL : "
        f"{rul_prediction:.4f} h"
    )

    print(
        f"Status        : "
        f"{status}"
    )

    print(
        f"Explanation   : "
        f"{explanation_target}"
    )

    print(
        f"Risk factors  : "
        f"{len(risk_factors)}"
    )

    print(
        f"[SAVE] {OUTPUT_PATH}"
    )

    print()
    print("=" * 80)

    print(
        "[PASS] RUL prediction available"
    )

    print(
        "[PASS] Risk scores available"
    )

    print(
        "[PASS] Status available"
    )

    print(
        "[PASS] Risk factors available"
    )

    print(
        "[PASS] Final prediction contract validated"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()