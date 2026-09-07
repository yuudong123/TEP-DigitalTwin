from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VERSION = "v1.0.0"

SOURCE_MODEL_DIR = (
    PROJECT_ROOT
    / "models"
    / "candidates"
    / "05-temporal"
)

THRESHOLD_PATH = (
    PROJECT_ROOT
    / "reports"
    / "05-temporal"
    / "thresholds.json"
)

METRICS_PATH = (
    PROJECT_ROOT
    / "reports"
    / "05-temporal"
    / "temporal_metrics.csv"
)

PRODUCTION_DIR = (
    PROJECT_ROOT
    / "models"
    / "production"
    / VERSION
)

MODEL_FILES = [
    "rul_hours.json",
    "failure_within_4h.json",
    "failure_within_2h.json",
    "failure_within_1h.json",
]


def get_git_commit() -> str | None:
    try:
        result = subprocess.run(
            [
                "git",
                "rev-parse",
                "HEAD",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        return result.stdout.strip()

    except Exception:
        return None


def load_thresholds() -> dict:
    with THRESHOLD_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def load_metrics() -> dict:
    df = pd.read_csv(METRICS_PATH)

    result = {}

    for _, row in df.iterrows():
        target = row["target"]

        if target == "rul_hours":
            result[target] = {
                "test_mae": float(
                    row["test_mae"]
                ),
                "test_rmse": float(
                    row["test_rmse"]
                ),
                "test_r2": float(
                    row["test_r2"]
                ),
            }

        else:
            result[target] = {
                "test_average_precision": float(
                    row["test_average_precision"]
                ),
                "test_roc_auc": float(
                    row["test_roc_auc"]
                ),
                "test_f1": float(
                    row["test_f1"]
                ),
                "event_detection_rate": float(
                    row["event_detection_rate"]
                ),
            }

    return result


def main() -> None:
    print("=" * 80)
    print("CREATE PRODUCTION MODEL VERSION")
    print("=" * 80)

    PRODUCTION_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 모델 복사
    for filename in MODEL_FILES:
        source = SOURCE_MODEL_DIR / filename

        if not source.exists():
            raise FileNotFoundError(
                f"모델 파일이 없습니다: {source}"
            )

        destination = (
            PRODUCTION_DIR / filename
        )

        shutil.copy2(
            source,
            destination,
        )

        print(f"[COPY] {filename}")

    # threshold 복사
    if not THRESHOLD_PATH.exists():
        raise FileNotFoundError(
            f"threshold 파일이 없습니다: {THRESHOLD_PATH}"
        )

    shutil.copy2(
        THRESHOLD_PATH,
        PRODUCTION_DIR
        / "thresholds.json",
    )

    print("[COPY] thresholds.json")

    thresholds = load_thresholds()
    metrics = load_metrics()

    metadata = {
        "version": VERSION,

        "created_at_utc": (
            datetime.now(timezone.utc)
            .isoformat()
        ),

        "git_commit": get_git_commit(),

        "model_family": "XGBoost",

        "feature_set": "temporal",

        "feature_count": 728,

        "sampling_interval_minutes": 3,

        "warmup_minutes": 60,

        "training_cases": [
            "case1",
            "case2",
            "case3",
            "case4",
            "case5",
            "case6",
        ],

        "models": {
            "rul": "rul_hours.json",

            "failure_within_4h":
                "failure_within_4h.json",

            "failure_within_2h":
                "failure_within_2h.json",

            "failure_within_1h":
                "failure_within_1h.json",
        },

        "thresholds": thresholds,

        "test_metrics": metrics,

        "source_candidate":
            "models/candidates/05-temporal",
    }

    metadata_path = (
        PRODUCTION_DIR
        / "metadata.json"
    )

    with metadata_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metadata,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(f"[SAVE] {metadata_path}")

    print()
    print(f"Version       : {VERSION}")
    print("Feature set   : temporal")
    print("Feature count : 728")
    print(f"Git commit    : {metadata['git_commit']}")

    print()
    print("[PASS] Production model version created")


if __name__ == "__main__":
    main()