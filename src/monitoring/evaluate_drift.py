"""분리된 trajectory의 정상 구간을 Drift Monitor와 동일한 방식으로 평가한다.

이 도구의 alert rate는 validation/test에 Drift 라벨이 없을 때의 *정상성 proxy*다.
따라서 결과만으로 운영 오탐률을 확정하지 않고, 기준 구간 품질 검토와 함께 사용한다.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .main import DriftMonitor, load_reference


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPLITS = {"validation", "test"}
ALERT_STATUSES = {"DRIFT", "CONFIRMED_DRIFT"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _trajectory_ids(manifest: Path, split: str) -> dict[str, set[int]]:
    if split not in SPLITS:
        raise ValueError(f"지원하지 않는 split입니다: {split}")
    selected: dict[str, set[int]] = {}
    with manifest.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if row.get("split") != split:
                continue
            case_name = row["case"]
            selected.setdefault(case_name, set()).add(int(float(row["Id"])))
    if not selected or any(not ids for ids in selected.values()):
        raise ValueError(f"{split} trajectory가 없습니다.")
    return selected


def _read_trajectories(
    raw_dir: Path,
    selected: dict[str, set[int]],
) -> dict[tuple[str, int], list[dict[str, str]]]:
    trajectories: dict[tuple[str, int], list[dict[str, str]]] = {}
    for case_name, ids in selected.items():
        path = raw_dir / f"{case_name}.csv"
        if not path.exists():
            raise FileNotFoundError(f"원본 데이터를 찾을 수 없습니다: {path}")
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                trajectory_id = int(float(row["Id"]))
                if trajectory_id in ids:
                    trajectories.setdefault((case_name, trajectory_id), []).append(row)
    missing = set((case, trajectory) for case, ids in selected.items() for trajectory in ids) - set(trajectories)
    if missing:
        raise ValueError(f"원본에 없는 trajectory가 있습니다: {sorted(missing)}")
    for rows in trajectories.values():
        rows.sort(key=lambda row: float(row["Time"]))
    return trajectories


def _sensor_message(case_name: str, trajectory_id: int, sequence: int, row: dict[str, str]) -> dict[str, Any]:
    return {
        "trajectory_key": f"{case_name}::{trajectory_id}",
        "case": case_name,
        "trajectory_id": trajectory_id,
        "sequence": sequence,
        "timestamp_hours": float(row["Time"]),
        "values": {name: float(value) for name, value in row.items() if name not in {"Id", "Time"}},
    }


def evaluate(
    *,
    raw_dir: Path,
    manifest_path: Path,
    reference_path: Path,
    split: str,
    minimum_timestamp_hours: float = 30.0,
    window_size: int = 120,
    min_samples: int = 20,
    check_interval_seconds: float = 21600.0,
    simulation_step_seconds: float = 180.0,
) -> dict[str, Any]:
    reference_version, references = load_reference(reference_path)
    selected = _trajectory_ids(manifest_path, split)
    trajectories = _read_trajectories(raw_dir, selected)
    features = list(next(iter(references.values())).keys())
    simulated_clock = [0.0]
    monitor = DriftMonitor(
        features=features,
        references=references,
        reference_version=reference_version,
        model_version="v1.0.0",
        # 원본 한 행은 0.05시간(180초) 간격이다. 통계 계산량을 제한하기 위해
        # 기본 6시간 간격으로 평가하며, 이는 운영 오탐률 확정용이 아닌 후보 선별용이다.
        check_interval_seconds=check_interval_seconds,
        minimum_timestamp_hours=minimum_timestamp_hours,
        retraining_enabled=False,
        retraining_state_path=PROJECT_ROOT / "logs" / "drift-evaluation-state.json",
        window_size=window_size,
        min_samples=min_samples,
        clock=lambda: simulated_clock[0],
    )

    status_counts: dict[str, int] = {}
    per_case: dict[str, dict[str, int]] = {}
    evaluated_windows = 0
    alerts = 0
    max_ratio = 0.0
    feature_alert_counts = {feature: 0 for feature in features}
    for (case_name, trajectory_id), rows in sorted(trajectories.items()):
        case_stats = per_case.setdefault(case_name, {"trajectories": 0, "windows": 0, "alerts": 0})
        case_stats["trajectories"] += 1
        for sequence, row in enumerate(rows):
            simulated_clock[0] += simulation_step_seconds
            event = monitor.process(_sensor_message(case_name, trajectory_id, sequence, row))
            if event is None or event["status"] == "INSUFFICIENT_DATA":
                continue
            status = str(event["status"])
            status_counts[status] = status_counts.get(status, 0) + 1
            evaluated_windows += 1
            case_stats["windows"] += 1
            ratio = float(event["drifted_feature_ratio"])
            max_ratio = max(max_ratio, ratio)
            for feature_result in event["features"]:
                if feature_result["drifted"]:
                    feature_alert_counts[feature_result["feature"]] += 1
            if status in ALERT_STATUSES:
                alerts += 1
                case_stats["alerts"] += 1

    return {
        "schema_version": "1.0",
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation_type": "normality_proxy",
        "split": split,
        "reference_version": reference_version,
        "reference_sha256": _sha256(reference_path),
        "minimum_timestamp_hours": minimum_timestamp_hours,
        "window_size": window_size,
        "min_samples": min_samples,
        "check_interval_seconds": check_interval_seconds,
        "simulation_step_seconds": simulation_step_seconds,
        "trajectory_count": sum(item["trajectories"] for item in per_case.values()),
        "evaluated_windows": evaluated_windows,
        "alert_windows": alerts,
        "alert_window_rate": alerts / evaluated_windows if evaluated_windows else None,
        "max_drifted_feature_ratio": max_ratio,
        "feature_alert_rates": [
            {
                "feature": feature,
                "alert_windows": count,
                "alert_rate": count / evaluated_windows if evaluated_windows else None,
            }
            for feature, count in sorted(
                feature_alert_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "status_counts": status_counts,
        "per_case": per_case,
        "interpretation": "라벨 없는 split의 정상성 proxy이며 운영 오탐률 확정값이 아님",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Drift Monitor validation/test 평가")
    parser.add_argument("--raw-dir", type=Path, default=PROJECT_ROOT / "data" / "raw" / "TEP")
    parser.add_argument("--manifest", type=Path, default=PROJECT_ROOT / "data" / "metadata" / "split_manifest.csv")
    parser.add_argument("--reference", type=Path, default=PROJECT_ROOT / "models" / "monitoring" / "drift-reference-v1.0.0.json")
    parser.add_argument("--split", choices=sorted(SPLITS), default="validation")
    parser.add_argument("--check-interval-seconds", type=float, default=21600.0)
    parser.add_argument("--simulation-step-seconds", type=float, default=180.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(
        raw_dir=args.raw_dir,
        manifest_path=args.manifest,
        reference_path=args.reference,
        split=args.split,
        check_interval_seconds=args.check_interval_seconds,
        simulation_step_seconds=args.simulation_step_seconds,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
