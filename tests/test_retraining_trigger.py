from datetime import datetime, timedelta, timezone

from src.monitoring.retraining_trigger import RetrainingTrigger


class MutableClock:
    def __init__(self):
        self.now = datetime(2026, 9, 21, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


def test_trigger_requires_all_conditions(tmp_path):
    clock = MutableClock()
    trigger = RetrainingTrigger(tmp_path / "state.json", clock=clock)

    assert trigger.evaluate(
        case_name="case1", drift_status="DRIFT", quality_valid=True
    ).reason == "confirmed_drift_required"
    assert trigger.evaluate(
        case_name="case1", drift_status="CONFIRMED_DRIFT", quality_valid=False
    ).reason == "data_quality_failed"


def test_disabled_trigger_does_not_write_state(tmp_path):
    state_path = tmp_path / "state.json"
    trigger = RetrainingTrigger(state_path, enabled=False)

    decision = trigger.evaluate(
        case_name="case1",
        drift_status="CONFIRMED_DRIFT",
        quality_valid=True,
    )

    assert decision.reason == "retraining_disabled"
    assert not state_path.exists()


def test_duplicate_request_is_blocked_until_cooldown_expires(tmp_path):
    state_path = tmp_path / "state.json"
    clock = MutableClock()
    trigger = RetrainingTrigger(state_path, clock=clock)

    first = trigger.evaluate(
        case_name="case1",
        drift_status="CONFIRMED_DRIFT",
        quality_valid=True,
    )
    second = trigger.evaluate(
        case_name="case1",
        drift_status="CONFIRMED_DRIFT",
        quality_valid=True,
    )
    clock.now += timedelta(hours=24)
    third = trigger.evaluate(
        case_name="case1",
        drift_status="CONFIRMED_DRIFT",
        quality_valid=True,
    )

    assert first.requested is True
    assert second.reason == "cooldown_active"
    assert second.cooldown_remaining_seconds == 24 * 60 * 60
    assert third.requested is True


def test_persisted_state_blocks_request_after_restart(tmp_path):
    state_path = tmp_path / "state.json"
    clock = MutableClock()
    first = RetrainingTrigger(state_path, clock=clock)
    first.evaluate(
        case_name="case2",
        drift_status="CONFIRMED_DRIFT",
        quality_valid=True,
    )

    restarted = RetrainingTrigger(state_path, clock=clock)
    decision = restarted.evaluate(
        case_name="case2",
        drift_status="CONFIRMED_DRIFT",
        quality_valid=True,
    )

    assert decision.reason == "cooldown_active"


def test_cooldown_is_independent_per_case(tmp_path):
    trigger = RetrainingTrigger(tmp_path / "state.json", clock=MutableClock())
    trigger.evaluate(
        case_name="case1",
        drift_status="CONFIRMED_DRIFT",
        quality_valid=True,
    )

    decision = trigger.evaluate(
        case_name="case2",
        drift_status="CONFIRMED_DRIFT",
        quality_valid=True,
    )

    assert decision.requested is True
