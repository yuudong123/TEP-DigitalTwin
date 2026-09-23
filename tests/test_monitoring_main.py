from pathlib import Path

from src.monitoring.drift_detector import DriftThresholds
from src.monitoring.main import DriftMonitor, load_reference, settings_from_environment
from src.monitoring.event_schema import validate_drift_event


def message(sequence: int, timestamp: float, trajectory_id: int = 1) -> dict:
    values = {"a": float(sequence), "b": float(sequence) + 0.5}
    return {
        "trajectory_key": f"case1::{trajectory_id}",
        "case": "case1",
        "trajectory_id": trajectory_id,
        "sequence": sequence,
        "timestamp_hours": timestamp,
        "values": values,
    }


def test_monitor_emits_schema_valid_warmup_and_normal_events(tmp_path):
    monitor = DriftMonitor(
        features=["a", "b"],
        references={"case1": {"a": [0.0, 1.0], "b": [0.5, 1.5]}},
        reference_version="v1.0.0",
        model_version="v1.0.0",
        check_interval_seconds=0,
        minimum_timestamp_hours=0,
        retraining_state_path=tmp_path / "state.json",
        window_size=3,
        min_samples=2,
        thresholds=DriftThresholds(min_samples=2),
    )

    first = monitor.process(message(0, 0.0))
    second = monitor.process(message(1, 0.05))

    validate_drift_event(first)
    validate_drift_event(second)
    assert first["status"] == "INSUFFICIENT_DATA"
    assert second["status"] == "NORMAL"
    assert second["window"]["samples"] == 2


def test_monitor_resets_after_sequence_gap(tmp_path):
    monitor = DriftMonitor(
        features=["a", "b"],
        references={"case1": {"a": [0.0, 1.0], "b": [0.5, 1.5]}},
        reference_version="v1.0.0",
        model_version="v1.0.0",
        check_interval_seconds=0,
        minimum_timestamp_hours=0,
        retraining_state_path=tmp_path / "state.json",
        window_size=3,
        min_samples=2,
        thresholds=DriftThresholds(min_samples=2),
    )
    monitor.process(message(0, 0.0))
    event = monitor.process(message(2, 0.1))

    assert event["status"] == "INSUFFICIENT_DATA"
    assert event["reason"] == "sequence_gap"
    assert event["window"]["samples"] == 1


def test_monitor_does_not_compare_before_reference_start(tmp_path):
    monitor = DriftMonitor(
        features=["a", "b"],
        references={"case1": {"a": [0.0, 1.0], "b": [0.5, 1.5]}},
        reference_version="v1.0.0",
        model_version="v1.0.0",
        check_interval_seconds=0,
        minimum_timestamp_hours=30,
        retraining_state_path=tmp_path / "state.json",
        window_size=3,
        min_samples=2,
        thresholds=DriftThresholds(min_samples=2),
    )

    assert monitor.process(message(0, 0.0))["reason"] == "before_reference_window"
    before = monitor.process(message(1, 0.05))
    assert before["reason"] == "before_reference_window"
    after = monitor.process(message(2, 30.0))
    assert after["window"]["samples"] == 1


def test_monitor_confirmation_is_isolated_per_trajectory(tmp_path):
    thresholds = DriftThresholds(min_samples=2, drift_ratio=0.20)
    monitor = DriftMonitor(
        features=["a", "b"],
        references={"case1": {"a": [0.0, 1.0], "b": [0.5, 1.5]}},
        reference_version="v1.0.0",
        model_version="v1.0.0",
        check_interval_seconds=0,
        minimum_timestamp_hours=0,
        retraining_state_path=tmp_path / "state.json",
        window_size=2,
        min_samples=2,
        thresholds=thresholds,
    )

    # 각 trajectory는 두 번의 Drift만 보았으므로, 서로 섞여 CONFIRMED가 되면 안 된다.
    for sequence in range(2):
        monitor.process(message(sequence, float(sequence), trajectory_id=1))
        monitor.process(message(sequence, float(sequence), trajectory_id=2))
    event_1 = monitor.process(message(2, 2.0, trajectory_id=1))
    event_2 = monitor.process(message(2, 2.0, trajectory_id=2))
    assert event_1["status"] != "CONFIRMED_DRIFT"
    assert event_2["status"] != "CONFIRMED_DRIFT"


def test_real_reference_file_has_six_cases_and_52_features():
    version, references = load_reference(
        Path("models/monitoring/drift-reference-v1.0.0.json")
    )

    assert version == "v1.0.0"
    assert set(references) == {f"case{number}" for number in range(1, 7)}
    assert all(len(features) == 52 for features in references.values())


def test_retraining_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("RETRAIN_ENABLED", raising=False)
    assert settings_from_environment().retraining_enabled is False
