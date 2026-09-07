from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VERSION = "v1.0.0"

OUTPUT_PATH = (
    PROJECT_ROOT
    / "models"
    / "production"
    / VERSION
    / "prediction_schema.json"
)


def main() -> None:
    schema = {
        "schema_version": "1.0",

        "model_version": "string",

        "trajectory_key": "string",

        "timestamp_hours": "number",

        "rul": {
            "hours": "number",
        },

        "risk": {
            "failure_within_4h": {
                "score": "number",
                "threshold": "number",
                "alert": "boolean",
            },

            "failure_within_2h": {
                "score": "number",
                "threshold": "number",
                "alert": "boolean",
            },

            "failure_within_1h": {
                "score": "number",
                "threshold": "number",
                "alert": "boolean",
            },
        },

        "status": (
            "NORMAL | CAUTION | WARNING | CRITICAL"
        ),

        "explanation_model": (
            "failure_within_4h | "
            "failure_within_2h | "
            "failure_within_1h"
        ),

        "top_risk_factors": [
            {
                "rank": "integer",
                "feature": "string",
                "source_feature": "string",
                "transform": "string",
                "window_minutes": (
                    "integer | null"
                ),
                "shap_value": "number",
            }
        ],
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            schema,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"[SAVE] {OUTPUT_PATH}"
    )

    print(
        "[PASS] Prediction schema saved"
    )


if __name__ == "__main__":
    main()