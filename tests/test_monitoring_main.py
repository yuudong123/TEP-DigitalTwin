from pathlib import Path

from src.monitoring.drift_detector import DriftThresholds
from src.monitoring.main import DriftMonitor, load_reference
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


def test_real_reference_file_has_six_cases_and_52_features():
    version, references = load_reference(
        Path("models/monitoring/drift-reference-v1.0.0.json")
    )

    assert version == "v1.0.0"
    assert set(references) == {f"case{number}" for number in range(1, 7)}
    assert all(len(features) == 52 for features in references.values())
