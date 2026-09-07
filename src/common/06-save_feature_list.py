from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VERSION = "v1.0.0"

SOURCE_SCHEMA_PATH = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "temporal_feature_schema.csv"
)

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

FEATURE_SCHEMA_PATH = (
    PRODUCTION_DIR
    / "feature_schema.csv"
)

METADATA_PATH = (
    PRODUCTION_DIR
    / "metadata.json"
)

EXPECTED_FEATURE_COUNT = 728


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
    )


def main() -> None:
    print("=" * 80)
    print("SAVE PRODUCTION FEATURE LIST")
    print("=" * 80)

    if not SOURCE_SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Temporal feature schema가 없습니다: {SOURCE_SCHEMA_PATH}"
        )

    if not PRODUCTION_DIR.exists():
        raise FileNotFoundError(
            f"Production model directory가 없습니다: {PRODUCTION_DIR}"
        )

    schema = pd.read_csv(
        SOURCE_SCHEMA_PATH
    )

    schema["model_feature"] = parse_bool(
        schema["model_feature"]
    )

    model_schema = (
        schema[
            schema["model_feature"]
        ]
        .copy()
        .reset_index(drop=True)
    )

    features = (
        model_schema["feature"]
        .tolist()
    )

    if len(features) != EXPECTED_FEATURE_COUNT:
        raise ValueError(
            "Feature count 오류: "
            f"expected={EXPECTED_FEATURE_COUNT}, "
            f"actual={len(features)}"
        )

    if len(features) != len(set(features)):
        raise ValueError(
            "Feature 이름에 중복이 있습니다."
        )

    # --------------------------------------------------------
    # Exact ordered feature list
    # --------------------------------------------------------

    feature_payload = {
        "model_version": VERSION,
        "feature_count": len(features),
        "order_required": True,
        "features": features,
    }

    with FEATURE_LIST_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            feature_payload,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"[SAVE] {FEATURE_LIST_PATH}"
    )

    # --------------------------------------------------------
    # Feature schema snapshot
    # --------------------------------------------------------

    model_schema.to_csv(
        FEATURE_SCHEMA_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"[SAVE] {FEATURE_SCHEMA_PATH}"
    )

    # --------------------------------------------------------
    # Update production metadata
    # --------------------------------------------------------

    if METADATA_PATH.exists():
        with METADATA_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            metadata = json.load(file)

        metadata["feature_count"] = len(features)
        metadata["feature_list_file"] = "feature_list.json"
        metadata["feature_schema_file"] = "feature_schema.csv"

        with METADATA_PATH.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                metadata,
                file,
                indent=2,
                ensure_ascii=False,
            )

        print(
            "[UPDATE] metadata.json"
        )

    print()
    print(f"Feature count : {len(features)}")
    print(f"First feature : {features[0]}")
    print(f"Last feature  : {features[-1]}")

    print()
    print("[PASS] Production feature list saved")


if __name__ == "__main__":
    main()