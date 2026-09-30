"""Train의 안정 구간 창 통계로 변화 감시 기준 후보를 만든다(운영 자동 적용 없음)."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np

from .drift_detector import DriftDetector
from .main import load_reference
from .reference_builder import PROJECT_ROOT, file_sha256, load_train_ids


def limits_from_scores(psi: list[float], ks: list[float]) -> dict[str, float]:
    if not psi or len(psi) != len(ks):
        raise ValueError("Missing or mismatched calibration scores")
    if not np.all(np.isfinite(psi)) or not np.all(np.isfinite(ks)):
        raise ValueError("Calibration scores must be finite")
    return {
        "psi": max(0.25, float(np.quantile(psi, 0.99, method="higher"))),
        "ks": max(0.15, float(np.quantile(ks, 0.99, method="higher"))),
    }


def stable_runs(path: Path, ids: set[int], features: list[str]) -> dict[int, np.ndarray]:
    """Train Id와 [30,60)만 읽어 600개의 연속 유효 관측인지 검사한다."""
    rows: dict[int, list[tuple[float, list[float]]]] = {key: [] for key in ids}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            key = int(float(row["Id"]))
            hour = float(row["Time"])
            if key in rows and 30 <= hour < 60:
                rows[key].append((hour, [float(row[f]) for f in features]))
    result = {}
    for key, observations in rows.items():
        # 원본의 누락·역전을 정렬로 숨기지 않는다.
        times = np.array([row[0] for row in observations])
        values = np.array([row[1] for row in observations])
        if len(times) != 600 or not np.allclose(times, np.arange(600) * .05 + 30, rtol=0, atol=1e-7):
            raise ValueError(f"Incomplete or unordered stable interval: {path.name}::{key}")
        if not np.all(np.isfinite(values)):
            raise ValueError(f"Nonfinite stable input: {path.name}::{key}")
        result[key] = values
    return result


def fit(raw_dir: Path, manifest: Path, reference_path: Path) -> dict:
    version, references = load_reference(reference_path)
    source_reference = json.loads(reference_path.read_text(encoding="utf-8"))
    if source_reference["source"]["split_manifest_sha256"] != file_sha256(manifest):
        raise ValueError("Reference and calibration split manifests differ")
    ids = load_train_ids(manifest, references)
    features = list(next(iter(references.values())))
    cases = {}
    for case, reference in references.items():
        runs = stable_runs(raw_dir / f"{case}.csv", ids[case], features)
        scores = {f: {"psi": [], "ks": []} for f in features}
        legacy_alerts = 0
        for values in runs.values():
            detector = DriftDetector()
            for start in range(0, 600, 120):
                current = {f: values[start:start + 120, j] for j, f in enumerate(features)}
                detected = detector.detect(reference, current)
                legacy_alerts += detected.status in {"DRIFT", "CONFIRMED_DRIFT"}
                for item in detected.features:
                    scores[item.feature]["psi"].append(item.psi)
                    scores[item.feature]["ks"].append(item.ks_statistic)
        limits = {f: limits_from_scores(**scores[f]) for f in features}
        windows = len(runs) * 5
        cases[case] = {
            "trajectory_ids": sorted(runs), "windows": windows,
            "legacy_alert_windows": legacy_alerts,
            "legacy_alert_window_rate": legacy_alerts / windows,
            "limits": limits,
            "diagnostics": {
                f: {"median_psi": float(np.median(scores[f]["psi"])),
                    "median_ks": float(np.median(scores[f]["ks"]))}
                for f in features
            },
        }
        print(f"{case}: train windows={windows}, legacy alerts={legacy_alerts}", flush=True)
    return {
        "schema_version": "1.0", "method": "train_stable_joint_psi_ks_p99",
        "created_at": datetime.now(timezone.utc).isoformat(), "split": "train",
        "reference_version": version, "reference_sha256": file_sha256(reference_path),
        "manifest_sha256": file_sha256(manifest), "window_size": 120,
        "stable_interval_hours": [30, 60], "quantile": .99,
        "rule": "psi > limit AND ks > limit; no p-value gate",
        "cases": cases,
    }


def load_limits(path: Path, reference_path: Path, manifest: Path, window_size: int) -> dict:
    profile = json.loads(path.read_text(encoding="utf-8"))
    if (profile.get("schema_version") != "1.0" or profile.get("split") != "train"
        or profile.get("method") != "train_stable_joint_psi_ks_p99"
        or profile.get("window_size") != window_size):
        raise ValueError("Unsupported calibration profile")
    if (profile.get("reference_sha256") != file_sha256(reference_path)
        or profile.get("manifest_sha256") != file_sha256(manifest)):
        raise ValueError("Calibration/reference/manifest hash mismatch")
    _, references = load_reference(reference_path)
    if set(profile["cases"]) != set(references):
        raise ValueError("Calibration case mismatch")
    result = {}
    for case, reference in references.items():
        limits = profile["cases"][case]["limits"]
        if set(limits) != set(reference):
            raise ValueError("Calibration feature mismatch")
        for pair in limits.values():
            if (not np.isfinite(pair["psi"]) or pair["psi"] < .25
                or not np.isfinite(pair["ks"]) or not .15 <= pair["ks"] <= 1):
                raise ValueError("Invalid calibration thresholds")
        result[case] = limits
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=PROJECT_ROOT / "data/metadata/split_manifest.csv")
    parser.add_argument("--reference", type=Path, default=PROJECT_ROOT / "models/monitoring/drift-reference-v1.0.0.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    profile = fit(args.raw_dir, args.manifest, args.reference)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
