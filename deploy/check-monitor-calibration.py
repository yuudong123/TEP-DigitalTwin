"""집컴에서 격리된 Kafka topic/container로 기준 후보의 end-to-end 동작을 확인한다."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from confluent_kafka import Consumer, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from kafka.message_schema import build_sensor_message
from src.monitoring.event_schema import validate_drift_event


def check(root: Path, raw_dir: Path, profile: Path, docker: Path, output: Path) -> None:
    tag = uuid4().hex[:12]
    topics = [f"tep-monitor-check-{tag}-sensor", f"tep-monitor-check-{tag}-event"]
    container = f"tep-monitor-check-{tag}"
    admin = AdminClient({"bootstrap.servers": "localhost:9092"})
    consumer = None
    started = False
    result = {"tag": tag, "success": False, "schema_errors": 0}
    try:
        for future in admin.create_topics([NewTopic(t, 1, 1) for t in topics]).values():
            future.result(timeout=20)
        data = json.loads(profile.read_text(encoding="utf-8"))
        reference = json.loads((root / "models/monitoring/drift-reference-v1.0.0.json").read_text(encoding="utf-8"))
        case = "case1"
        run_id = data["cases"][case]["trajectory_ids"][0]
        rows = []
        with (raw_dir / f"{case}.csv").open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                if int(float(row["Id"])) == run_id and 30 <= float(row["Time"]) < 37:
                    rows.append(row)
                    if len(rows) == 122:
                        break
        if len(rows) != 122:
            raise ValueError("Missing smoke-test stable rows")
        mounts = [
            f"type=bind,src={root / 'src'},dst=/app/src,readonly",
            f"type=bind,src={profile},dst=/app/models/monitoring/calibration.json,readonly",
        ]
        command = [str(docker), "run", "-d", "--name", container,
                   "--network", "tep-network"]
        for mount in mounts:
            command += ["--mount", mount]
        for key, value in {
            "PYTHONUNBUFFERED": "1", "KAFKA_BOOTSTRAP_SERVERS": "kafka:19092",
            "KAFKA_SENSOR_TOPIC": topics[0], "KAFKA_DRIFT_TOPIC": topics[1],
            "DRIFT_CONSUMER_GROUP": container, "DRIFT_CHECK_INTERVAL_SECONDS": "0",
            "DRIFT_CALIBRATION_PATH": "models/monitoring/calibration.json",
            "RETRAIN_ENABLED": "false",
        }.items():
            command += ["-e", f"{key}={value}"]
        subprocess.run(command + ["tep_digitaltwin-monitor:latest"], check=True, capture_output=True)
        started = True
        # Kafka 구독 assignment가 된 것을 group 상태로 확인한 뒤 입력한다.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            described = admin.describe_consumer_groups([container])[container].result(timeout=5)
            if any(member.assignment.topic_partitions for member in described.members):
                break
            time.sleep(.5)
        else:
            raise RuntimeError("Monitor consumer assignment timed out")
        producer = Producer({"bootstrap.servers": "localhost:9092"})
        errors = []
        for shifted, count in ((False, 120), (True, 122)):
            for sequence, row in enumerate(rows[:count]):
                payload = dict(row)
                if shifted:
                    payload["Id"] = str(run_id + 10000)
                    for f, summary in reference["cases"][case]["features"].items():
                        # 기준 최대값을 충분히 넘긴 인위적인 변화 대조군.
                        payload[f] = str(summary["max"] + max(abs(summary["max"]), 1) * 100)
                message = build_sensor_message(case, payload, sequence)
                producer.produce(topics[0], key=message["trajectory_key"],
                                 value=json.dumps(message).encode(),
                                 on_delivery=lambda error, _: errors.append(error) if error else None)
        if producer.flush(20) or errors:
            raise RuntimeError(f"Input delivery failed: {errors}")
        consumer = Consumer({"bootstrap.servers": "localhost:9092", "group.id": f"{container}-reader",
                             "auto.offset.reset": "earliest", "enable.auto.commit": False})
        consumer.subscribe([topics[1]])
        events = []
        deadline = time.monotonic() + 45
        while len(events) < 242 and time.monotonic() < deadline:
            item = consumer.poll(.5)
            if item is None:
                continue
            if item.error():
                raise RuntimeError(item.error())
            event = json.loads(item.value())
            validate_drift_event(event)
            events.append(event)
        if len(events) != 242:
            raise RuntimeError(f"Expected 242 events, got {len(events)}")
        normal = [event for event in events if event["trajectory_key"] == f"case1::{run_id}"]
        shifted = [event for event in events if event["trajectory_key"] == f"case1::{run_id + 10000}"]
        if normal[-1]["status"] != "NORMAL" or shifted[-1]["status"] != "CONFIRMED_DRIFT":
            raise RuntimeError("Stable/positive-control status check failed")
        if any(event["retraining_requested"] for event in events):
            raise RuntimeError("Unexpected retraining request")
        result.update(success=True, event_count=len(events),
                      states=dict(Counter(event["status"] for event in events)),
                      stable_last_status=normal[-1]["status"], shifted_last_status=shifted[-1]["status"],
                      retraining_requests=0)
    finally:
        if consumer:
            consumer.close()
        if started:
            subprocess.run([str(docker), "rm", "-f", container], capture_output=True, check=True)
        for future in admin.delete_topics(topics).values():
            future.result(timeout=20)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--docker", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    check(args.root, args.raw_dir, args.profile, args.docker, args.output)
