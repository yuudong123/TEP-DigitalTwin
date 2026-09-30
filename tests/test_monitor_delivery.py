import pytest
from types import SimpleNamespace
from unittest.mock import Mock

from src.monitoring.main import publish_event
from src.monitoring import main as runtime


class FakeProducer:
    def __init__(self, *, error=None, pending=0, call=True):
        self.error, self.pending, self.call = error, pending, call

    def produce(self, topic, **kwargs):
        self.topic, self.kwargs = topic, kwargs

    def flush(self, timeout):
        if self.call:
            self.kwargs["on_delivery"](self.error, None)
        return self.pending


def test_success_requires_broker_callback():
    producer = FakeProducer()
    publish_event(producer, "topic", "case1::1", {"sequence": 2})
    assert producer.kwargs["key"] == b"case1::1"


@pytest.mark.parametrize("kwargs", [
    {"error": "message timed out"}, {"pending": 1}, {"call": False},
])
def test_flush_zero_does_not_hide_terminal_delivery_failure(kwargs):
    with pytest.raises(RuntimeError):
        publish_event(FakeProducer(**kwargs), "topic", "case1::1", {"sequence": 2})


@pytest.mark.parametrize("error", [None, "broker rejected message"])
def test_runtime_commits_only_after_successful_delivery(monkeypatch, error):
    consumer = Mock()
    kafka_message = Mock()
    kafka_message.error.return_value = None
    consumer.poll.return_value = kafka_message
    consumer.commit.side_effect = lambda **_: setattr(runtime, "RUNNING", False)
    producer = FakeProducer(error=error)
    settings = SimpleNamespace(
        bootstrap_servers="unused", drift_topic="output", sensor_topic="input",
        reference_path="unused", model_version="v-test", check_interval_seconds=60,
        minimum_timestamp_hours=30, retraining_enabled=False, retraining_state_path="unused",
        consumer_group="test",
    )
    monkeypatch.setattr(runtime, "RUNNING", True)
    monkeypatch.setattr(runtime, "settings_from_environment", lambda: settings)
    monkeypatch.setattr(runtime, "load_reference", lambda _: ("v-test", {"case1": {"a": [0.]}}))
    monkeypatch.setattr(runtime, "ensure_topic", lambda *_: None)
    monkeypatch.setattr(runtime, "Consumer", lambda _: consumer)
    monkeypatch.setattr(runtime, "Producer", lambda _: producer)
    monitor = Mock()
    monitor.process.return_value = {"status": "NORMAL"}
    monkeypatch.setattr(runtime, "DriftMonitor", lambda **_: monitor)
    monkeypatch.setattr(runtime, "decode_sensor_message", lambda _: {
        "trajectory_key": "case1::1", "sequence": 0,
    })
    monkeypatch.setattr(runtime.signal, "signal", lambda *_: None)
    if error:
        with pytest.raises(RuntimeError, match="delivery failed"):
            runtime.main()
        consumer.commit.assert_not_called()
    else:
        runtime.main()
        consumer.commit.assert_called_once_with(message=kafka_message, asynchronous=False)
    consumer.close.assert_called_once()
