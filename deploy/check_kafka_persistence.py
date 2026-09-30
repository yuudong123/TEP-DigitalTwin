"""Isolated broker recreation drill; never touches tep-kafka or tep-kafka-data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from confluent_kafka import Consumer, Producer
from confluent_kafka.admin import AdminClient, NewTopic


def check(docker: str, port: int, output: Path) -> None:
    if port == 9092 or not 1024 <= port <= 65535:
        raise ValueError("Use a non-production host port")
    name = "tep-persistence-check-" + uuid4().hex[:12]
    volume = name + "-data"
    topic = "persistence-control"
    group = "persistence-reader"
    result = {"success": False, "isolated": True, "test_volume": volume,
              "scope": "container recreation; not host reboot or production-volume recovery"}
    created_volume = False
    created_container = False

    def run(*args):
        return subprocess.run([docker, *args], check=True, capture_output=True, text=True).stdout.strip()

    def start():
        nonlocal created_container
        args = ["run", "-d", "--name", name, "--hostname", name,
                "-p", f"127.0.0.1:{port}:9092", "--mount",
                f"type=volume,source={volume},target=/tmp/kraft-combined-logs"]
        settings = {
            "KAFKA_NODE_ID": "1", "KAFKA_PROCESS_ROLES": "broker,controller",
            "KAFKA_CONTROLLER_QUORUM_VOTERS": f"1@{name}:29093",
            "KAFKA_CONTROLLER_LISTENER_NAMES": "CONTROLLER",
            "KAFKA_LISTENERS": "EXTERNAL://:9092,CONTROLLER://:29093",
            "KAFKA_ADVERTISED_LISTENERS": f"EXTERNAL://localhost:{port}",
            "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP": "EXTERNAL:PLAINTEXT,CONTROLLER:PLAINTEXT",
            "KAFKA_INTER_BROKER_LISTENER_NAME": "EXTERNAL",
            "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR": "1",
            "KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS": "0",
            "KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR": "1",
            "KAFKA_TRANSACTION_STATE_LOG_MIN_ISR": "1",
            "KAFKA_LOG_DIRS": "/tmp/kraft-combined-logs",
            "CLUSTER_ID": "4L6g3nShT-eMCtK--X86sw",
        }
        for key, value in settings.items():
            args += ["-e", f"{key}={value}"]
        run(*args, "apache/kafka:4.1.0")
        created_container = True
        admin = AdminClient({"bootstrap.servers": f"localhost:{port}"})
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline:
            try:
                if admin.list_topics(timeout=2).brokers:
                    return admin
            except Exception:
                time.sleep(.5)
            state = run("inspect", name, "--format", "{{.State.Running}}")
            if state != "true":
                result["startup_failure_logs"] = run("logs", "--tail", "12", name)
                raise RuntimeError("Isolated broker exited during startup")
        raise RuntimeError("Isolated broker startup timed out")

    def read(count, *, commit=False):
        consumer = Consumer({"bootstrap.servers": f"localhost:{port}", "group.id": group,
                             "auto.offset.reset": "earliest", "enable.auto.commit": False})
        consumer.subscribe([topic])
        values = []
        deadline = time.monotonic() + 30
        try:
            while len(values) < count and time.monotonic() < deadline:
                message = consumer.poll(.5)
                if message is None:
                    continue
                if message.error():
                    raise RuntimeError(message.error())
                values.append(json.loads(message.value()))
                if commit:
                    consumer.commit(message=message, asynchronous=False)
            if len(values) != count:
                raise RuntimeError(f"Missing persisted messages: {len(values)}/{count}")
            return values
        finally:
            consumer.close()

    try:
        run("volume", "create", volume)
        created_volume = True
        # Newly created named volumes are root-owned; the image runs as uid 1000.
        run("run", "--rm", "--user", "0", "--mount",
            f"type=volume,source={volume},target=/tmp/kraft-combined-logs",
            "--entrypoint", "/bin/sh", "apache/kafka:4.1.0", "-c",
            "chown 1000:1000 /tmp/kraft-combined-logs")
        admin = start()
        admin.create_topics([NewTopic(topic, 1, 1)])[topic].result(timeout=20)
        producer = Producer({"bootstrap.servers": f"localhost:{port}", "acks": "all"})
        errors = []
        for index in range(3):
            producer.produce(topic, value=json.dumps({"sequence": index}),
                             on_delivery=lambda err, _: errors.append(str(err)) if err else None)
        if producer.flush(20) or errors:
            raise RuntimeError("Synthetic messages were not acknowledged")
        first = read(1, commit=True)
        if first != [{"sequence": 0}]:
            raise RuntimeError("Initial committed position mismatch")
        run("stop", "--time", "30", name)
        run("rm", name)
        created_container = False
        admin = start()
        if topic not in admin.list_topics(timeout=10).topics:
            raise RuntimeError("Topic metadata was lost after recreation")
        remaining = read(2)
        if remaining != [{"sequence": 1}, {"sequence": 2}]:
            raise RuntimeError("Messages or consumer offsets did not survive recreation")
        result.update(success=True, committed_sequence=0, resumed_sequences=[1, 2],
                      topic_preserved=True, messages_preserved=True, offset_preserved=True)
    finally:
        # Exact UUID objects created by this invocation only. No prune/down -v.
        if created_container:
            run("rm", "-f", name)
        if created_volume:
            run("volume", "rm", volume)
        result["test_resources_removed"] = True
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--port", type=int, default=19094)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    check(args.docker, args.port, args.output)
