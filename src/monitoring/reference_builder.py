from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_CASES = tuple(f"case{number}" for number in range(1, 7))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_monitored_features(feature_schema_path: Path) -> list[str]:
    with feature_schema_path.open(encoding="utf-8-sig", newline="") as source:
        rows = csv.DictReader(source)
        features = [
            row["column"]
            for row in rows
            if row["model_b_feature"].strip().lower() == "true"
        ]

    if len(features) != 52 or len(features) != len(set(features)):
        raise ValueError(
            f"감시 Feature는 중복 없이 52개여야 합니다: {len(features)}개"
        )
    return features


def load_train_ids(
    manifest_path: Path,
    cases: Iterable[str],
) -> dict[str, set[int]]:
    selected = {case_name: set() for case_name in cases}
    with manifest_path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            case_name = row["case"]
            if row["split"] == "train" and case_name in selected:
                selected[case_name].add(int(float(row["Id"])))

    missing_cases = [case_name for case_name, ids in selected.items() if not ids]
    if missing_cases:
        raise ValueError(f"train trajectory가 없는 case: {missing_cases}")
    return selected


def _sample_evenly(values: np.ndarray, limit: int) -> list[float]:
    if values.size <= limit:
        return values.tolist()
    indices = np.linspace(0, values.size - 1, limit, dtype=int)
    return values[indices].tolist()


def _feature_summary(values: list[float], missing_count: int, sample_limit: int) -> dict:
    finite = np.asarray(values, dtype=float)
    if finite.size == 0:
        raise ValueError("기준 구간의 유효한 Feature 값이 없습니다.")
    quantiles = np.quantile(finite, np.linspace(0.0, 1.0, 11))
    return {
        "count": int(finite.size),
        "missing_count": missing_count,
        "missing_rate": missing_count / (finite.size + missing_count),
        "mean": float(np.mean(finite)),
        "std": float(np.std(finite)),
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "quantile_edges": quantiles.tolist(),
        "reference_sample": _sample_evenly(finite, sample_limit),
    }


def build_case_reference(
    csv_path: Path,
    train_ids: set[int],
    features: list[str],
    start_hour: float,
    end_hour: float,
    sample_limit: int,
) -> dict:
    values = {feature: [] for feature in features}
    missing = {feature: 0 for feature in features}
    row_count = 0
    used_ids: set[int] = set()

    with csv_path.open(encoding="utf-8-sig", newline="") as source:
        rows = csv.DictReader(source)
        absent = set(features) - set(rows.fieldnames or [])
        if absent:
            raise ValueError(f"{csv_path.name}에 Feature가 없습니다: {sorted(absent)}")

        for row in rows:
            trajectory_id = int(float(row["Id"]))
            timestamp = float(row["Time"])
            if trajectory_id not in train_ids or not start_hour <= timestamp < end_hour:
                continue

            row_count += 1
            used_ids.add(trajectory_id)
            for feature in features:
                try:
                    value = float(row[feature])
                except (TypeError, ValueError):
                    missing[feature] += 1
                    continue
                if not math.isfinite(value):
                    missing[feature] += 1
                    continue
                values[feature].append(value)

    if used_ids != train_ids:
        absent_ids = sorted(train_ids - used_ids)
        raise ValueError(f"{csv_path.name} 기준 구간에 없는 train Id: {absent_ids}")

    return {
        "trajectory_count": len(used_ids),
        "row_count": row_count,
        "features": {
            feature: _feature_summary(values[feature], missing[feature], sample_limit)
            for feature in features
        },
    }


def build_reference(
    *,
    raw_dir: Path,
    manifest_path: Path,
    feature_schema_path: Path,
    output_path: Path,
    reference_version: str = "v1.0.0",
    cases: Iterable[str] = OFFICIAL_CASES,
    start_hour: float = 30.0,
    end_hour: float = 60.0,
    sample_limit: int = 1000,
) -> dict:
    case_names = tuple(cases)
    if start_hour >= end_hour:
        raise ValueError("기준 구간 시작은 종료보다 작아야 합니다.")
    if sample_limit < 20:
        raise ValueError("reference sample은 최소 20개여야 합니다.")

    features = load_monitored_features(feature_schema_path)
    train_ids = load_train_ids(manifest_path, case_names)
    case_references = {}
    for case_name in case_names:
        csv_path = raw_dir / f"{case_name}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"원본 데이터를 찾을 수 없습니다: {csv_path}")
        case_references[case_name] = build_case_reference(
            csv_path,
            train_ids[case_name],
            features,
            start_hour,
            end_hour,
            sample_limit,
        )

    reference = {
        "schema_version": "1.0",
        "reference_version": reference_version,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"start_hour": start_hour, "end_hour": end_hour},
        "split": "train",
        "monitored_feature_count": len(features),
        "features": features,
        "source": {
            "split_manifest_sha256": file_sha256(manifest_path),
            "feature_schema_sha256": file_sha256(feature_schema_path),
        },
        "cases": case_references,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(reference, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return reference


def main() -> None:
    parser = argparse.ArgumentParser(description="Drift case별 기준 분포 생성")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "TEP",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "models" / "monitoring" / "drift-reference-v1.0.0.json",
    )
    parser.add_argument("--reference-version", default="v1.0.0")
    parser.add_argument("--sample-limit", type=int, default=1000)
    args = parser.parse_args()

    reference = build_reference(
        raw_dir=args.raw_dir,
        manifest_path=PROJECT_ROOT / "data" / "metadata" / "split_manifest.csv",
        feature_schema_path=PROJECT_ROOT / "data" / "metadata" / "feature_schema.csv",
        output_path=args.output,
        reference_version=args.reference_version,
        sample_limit=args.sample_limit,
    )
    print(f"생성 완료: {args.output}")
    for case_name, case_reference in reference["cases"].items():
        print(
            f"{case_name}: trajectories={case_reference['trajectory_count']}, "
            f"rows={case_reference['row_count']}"
        )


if __name__ == "__main__":
    main()
