import pytest

from src.monitoring.window_manager import SlidingWindowManager


def sensor_message(
    sequence,
    timestamp,
    *,
    trajectory_id=1,
    case_name="case1",
    values=None,
):
    return {
        "trajectory_key": f"{case_name}::{trajectory_id}",
        "case": case_name,
        "trajectory_id": trajectory_id,
        "sequence": sequence,
        "timestamp_hours": timestamp,
        "values": values or {"a": sequence, "b": sequence + 0.5},
    }


def test_window_becomes_ready_and_keeps_latest_samples():
    manager = SlidingWindowManager(["a", "b"], window_size=3, min_samples=2)

    assert manager.add(sensor_message(0, 0.0)).ready is False
    assert manager.add(sensor_message(1, 0.05)).ready is True
    manager.add(sensor_message(2, 0.10))
    manager.add(sensor_message(3, 0.15))

    assert manager.current("case1::1") == {
        "a": [1.0, 2.0, 3.0],
        "b": [1.5, 2.5, 3.5],
    }


def test_trajectories_are_kept_independently():
    manager = SlidingWindowManager(["a", "b"], window_size=3, min_samples=2)
    manager.add(sensor_message(0, 0.0, trajectory_id=1))
    manager.add(sensor_message(0, 0.0, trajectory_id=2))

    assert manager.current("case1::1")["a"] == [0.0]
    assert manager.current("case1::2")["a"] == [0.0]


@pytest.mark.parametrize(
    ("second_sequence", "second_timestamp", "reason"),
    [
        (0, 0.05, "sequence_not_increasing"),
        (2, 0.10, "sequence_gap"),
        (1, 0.0, "timestamp_not_increasing"),
    ],
)
def test_discontinuity_resets_only_target_window(
    second_sequence,
    second_timestamp,
    reason,
):
    manager = SlidingWindowManager(["a", "b"], window_size=120, min_samples=20)
    manager.add(sensor_message(0, 0.0))

    update = manager.add(sensor_message(second_sequence, second_timestamp))

    assert update.reset_reason == reason
    assert update.sample_count == 1


def test_missing_or_non_finite_feature_is_rejected_without_changing_window():
    manager = SlidingWindowManager(["a", "b"], window_size=120, min_samples=20)
    manager.add(sensor_message(0, 0.0))

    with pytest.raises(ValueError, match="감시 Feature"):
        manager.add(sensor_message(1, 0.05, values={"a": 1.0}))
    with pytest.raises(ValueError, match="유한한 숫자"):
        manager.add(sensor_message(1, 0.05, values={"a": 1.0, "b": float("nan")}))

    assert manager.current("case1::1")["a"] == [0.0]
