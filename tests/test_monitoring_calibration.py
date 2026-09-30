import csv

import numpy as np
import pytest

from src.monitoring.calibration import limits_from_scores, stable_runs, load_limits
from src.monitoring.drift_detector import DriftDetector
from src.monitoring.main import DriftMonitor


def test_empirical_limits_keep_original_floors_and_use_upper_tail():
    assert limits_from_scores([0.01] * 100, [0.02] * 100) == {"psi": .25, "ks": .15}
    assert limits_from_scores([0.] * 99 + [4.], [0.] * 99 + [.9]) == {"psi": 4., "ks": .9}


def test_calibrated_rule_requires_both_metrics_and_detects_shift():
    reference = {"a": np.linspace(0, 1, 1000)}
    current = {"a": np.linspace(10, 11, 120)}
    vetoed = DriftDetector(feature_limits={"a": {"psi": .25, "ks": 1.0}})
    assert vetoed.detect(reference, current).status == "NORMAL"
    detector = DriftDetector(feature_limits={"a": {"psi": .25, "ks": .5}})
    for _ in range(3):
        result = detector.detect(reference, current)
    assert result.status == "CONFIRMED_DRIFT"
    assert detector.detect(reference, {"a": np.linspace(0, 1, 120)}).status == "NORMAL"


def test_stable_reader_excludes_other_ids_and_late_degradation(tmp_path):
    path = tmp_path / "case1.csv"
    with path.open("w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["Id", "Time", "a"])
        for i in range(601):
            writer.writerow([1, 30 + .05 * i, i if i < 600 else 999999])
        writer.writerow([2, 30, "not-a-number"])
    runs = stable_runs(path, {1}, ["a"])
    assert runs[1].shape == (600, 1)
    assert runs[1].max() == 599
    with pytest.raises(ValueError, match="Incomplete"):
        stable_runs(path, {3}, ["a"])


def test_profile_rejects_nontrain_and_mismatched_hash(tmp_path):
    import json
    path = tmp_path / "profile.json"
    profile = {"schema_version": "1.0", "split": "validation", "window_size": 120,
               "method": "train_stable_joint_psi_ks_p99"}
    path.write_text(json.dumps(profile))
    with pytest.raises(ValueError, match="Unsupported"):
        load_limits(path, path, path, 120)
    profile["split"] = "train"
    profile["reference_sha256"] = "wrong"
    path.write_text(json.dumps(profile))
    with pytest.raises(ValueError, match="hash mismatch"):
        load_limits(path, path, path, 120)


@pytest.mark.parametrize("samples,retrain,error", [
    (20, False, "120-sample"), (120, True, "retraining"),
])
def test_candidate_profile_cannot_use_small_windows_or_retraining(samples, retrain, error):
    with pytest.raises(ValueError, match=error):
        DriftMonitor(
            features=["a"], references={"case1": {"a": [0., 1.]}},
            reference_version="v-test", model_version="v-test", min_samples=samples,
            feature_limits_by_case={"case1": {"a": {"psi": .25, "ks": .15}}},
            retraining_enabled=retrain,
        )


@pytest.mark.parametrize("setting", ["check_interval_seconds", "minimum_timestamp_hours"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.])
def test_runtime_rejects_nonfinite_or_negative_timing(setting, value):
    with pytest.raises(ValueError):
        DriftMonitor(features=["a"], references={"case1": {"a": [0., 1.]}},
                     reference_version="v-test", model_version="v-test", **{setting: value})


def test_calibrated_runtime_cannot_include_startup_interval():
    with pytest.raises(ValueError, match="pre-30h"):
        DriftMonitor(features=["a"], references={"case1": {"a": [0., 1.]}},
                     reference_version="v-test", model_version="v-test", min_samples=120,
                     minimum_timestamp_hours=0, feature_limits_by_case={})
