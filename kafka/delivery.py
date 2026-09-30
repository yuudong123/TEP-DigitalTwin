"""A drained producer queue is not proof of successful delivery."""
import json


def publish_json(producer, topic: str, key: str, payload: dict, timeout: float = 10) -> None:
    outcome = []
    producer.produce(
        topic=topic, key=key.encode(),
        value=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(),
        on_delivery=lambda error, _message: outcome.append(error),
    )
    remaining = producer.flush(timeout)
    if remaining or not outcome:
        raise RuntimeError("Kafka delivery was not acknowledged")
    if outcome[0] is not None:
        raise RuntimeError(f"Kafka delivery failed: {outcome[0]}")
