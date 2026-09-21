"""Kafka replay topic preparation helpers."""

from confluent_kafka import KafkaError, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic


def ensure_topic(
    bootstrap_servers: str,
    topic: str,
    timeout_seconds: float = 10.0,
) -> bool:
    """Create the replay topic when it does not exist."""

    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    metadata = admin.list_topics(timeout=timeout_seconds)
    topic_metadata = metadata.topics.get(topic)

    if topic_metadata is not None and topic_metadata.error is None:
        return False

    futures = admin.create_topics(
        [
            NewTopic(
                topic,
                num_partitions=1,
                replication_factor=1,
            )
        ]
    )

    try:
        futures[topic].result(timeout=timeout_seconds)
    except KafkaException as error:
        kafka_error = error.args[0] if error.args else None

        if (
            kafka_error is not None
            and kafka_error.code() == KafkaError.TOPIC_ALREADY_EXISTS
        ):
            return False

        raise

    return True
