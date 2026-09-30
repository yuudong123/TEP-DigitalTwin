"""집컴에서 격리된 Kafka topic/container로 기준 후보의 end-to-end 동작을 확인한다."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from confluent_kafka import Consumer, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic, ConfigResource, ResourceType

from kafka.message_schema import build_sensor_message
from src.monitoring.event_schema import validate_drift_event


def check(root: Path, raw_dir: Path, profile: Path, docker: Path, output: Path,
          interval: float = 0, recovery: bool = False) -> None:
    if interval < 0 or (recovery and interval != 0):
        raise ValueError("Use separate checks for timing and recovery")
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
            "DRIFT_CONSUMER_GROUP": container, "DRIFT_CHECK_INTERVAL_SECONDS": str(interval),
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
        def send(shifted, sequence):
            row = rows[min(sequence, len(rows) - 1)]
            payload = dict(row)
            payload["Time"] = str(30 + sequence * .05)
            if shifted:
                payload["Id"] = str(run_id + 10000)
                for f, summary in reference["cases"][case]["features"].items():
                    # 기준 최대값을 충분히 넘긴 인위적인 변화 대조군.
                    payload[f] = str(summary["max"] + max(abs(summary["max"]), 1) * 100)
            message = build_sensor_message(case, payload, sequence)
            producer.produce(topics[0], key=message["trajectory_key"],
                             value=json.dumps(message).encode(),
                             on_delivery=lambda error, _: errors.append(error) if error else None)
        for shifted, count in ((False, 120), (True, 120 if interval else 122)):
            for sequence in range(count):
                send(shifted, sequence)
        if producer.flush(20) or errors:
            raise RuntimeError(f"Input delivery failed: {errors}")
        consumer = Consumer({"bootstrap.servers": "localhost:9092", "group.id": f"{container}-reader",
                             "auto.offset.reset": "earliest", "enable.auto.commit": False})
        consumer.subscribe([topics[1]])
        events = []
        def receive(count):
            deadline = time.monotonic() + 45
            while len(events) < count and time.monotonic() < deadline:
                item = consumer.poll(.5)
                if item is None:
                    continue
                if item.error():
                    raise RuntimeError(item.error())
                event = json.loads(item.value())
                validate_drift_event(event)
                events.append(event)
            if len(events) != count:
                raise RuntimeError(f"Expected {count} events, got {len(events)}")
        receive(240 if interval else 242)
        if interval:
            detections = [time.monotonic()]
            for sequence in (120, 121):
                time.sleep(interval + 1)
                send(True, sequence)
                if producer.flush(20) or errors:
                    raise RuntimeError("Timed input delivery failed")
                receive(len(events) + 1)
                detections.append(time.monotonic())
            result["check_interval_seconds"] = interval
            result["observed_detection_gaps_seconds"] = [
                round(b - a, 3) for a, b in zip(detections, detections[1:])]
        if len(events) != 242:
            raise RuntimeError(f"Expected 242 events, got {len(events)}")
        normal = [event for event in events if event["trajectory_key"] == f"case1::{run_id}"]
        shifted = [event for event in events if event["trajectory_key"] == f"case1::{run_id + 10000}"]
        if normal[-1]["status"] != "NORMAL" or shifted[-1]["status"] != "CONFIRMED_DRIFT":
            raise RuntimeError("Stable/positive-control status check failed")
        if any(event["retraining_requested"] for event in events):
            raise RuntimeError("Unexpected retraining request")
        profile_hash = hashlib.sha256(profile.read_bytes()).hexdigest()
        if any(event.get("calibration_sha256") != profile_hash for event in events):
            raise RuntimeError("Event calibration identity does not match loaded profile")
        result.update(success=True, event_count=len(events),
                      states=dict(Counter(event["status"] for event in events)),
                      stable_last_status=normal[-1]["status"], shifted_last_status=shifted[-1]["status"],
                      retraining_requests=0, calibration_sha256=profile_hash)
        if recovery:
            result["success"] = False
            # 전용 출력 topic의 최대 메시지 크기를 1 byte로 낮춰 발행 거부를 유도한다.
            # 운영 topic·broker·volume 설정은 변경하지 않는다.
            def set_size(value):
                resource = ConfigResource(ResourceType.TOPIC, topics[1],
                                          set_config={"max.message.bytes": str(value)})
                for future in admin.alter_configs([resource]).values():
                    future.result(timeout=20)
            def committed():
                probe = Consumer({"bootstrap.servers": "localhost:9092", "group.id": container})
                try:
                    return probe.committed([TopicPartition(topics[0], 0)], timeout=10)[0].offset
                finally:
                    probe.close()
            deadline = time.monotonic() + 10
            while committed() != 242 and time.monotonic() < deadline:
                time.sleep(.2)
            if committed() != 242:
                raise RuntimeError("Initial input offsets were not committed")
            set_size(1)
            time.sleep(2)
            send(True, 122)
            if producer.flush(20) or errors:
                raise RuntimeError("Failure-control input delivery failed")
            deadline = time.monotonic() + 35
            while time.monotonic() < deadline:
                state = subprocess.run([str(docker), "inspect", container,
                                        "--format", "{{.State.Running}}"],
                                       check=True, capture_output=True, text=True).stdout.strip()
                if state == "false":
                    break
                time.sleep(.5)
            else:
                result["failure_diagnostics"] = {
                    "committed": committed(),
                    "logs": subprocess.run([str(docker), "logs", "--tail", "12", container],
                                           capture_output=True, text=True).stdout,
                }
                raise RuntimeError("Monitor did not fail on rejected event delivery")
            failed_offset = committed()
            if failed_offset != 242:
                raise RuntimeError(f"Failed input was committed: {failed_offset}")
            set_size(1048588)
            subprocess.run([str(docker), "start", container], check=True, capture_output=True)
            receive(243)
            retried = events[-1]
            if retried["sequence"] != 122 or retried["status"] != "INSUFFICIENT_DATA":
                raise RuntimeError("Uncommitted input was not retried with safe warmup")
            # 재시작 후 119+2개를 더 넣어 창 완성과 연속 3회 판정을 확인한다.
            for sequence in range(123, 244):
                send(True, sequence)
            if producer.flush(20) or errors:
                raise RuntimeError("Recovery input delivery failed")
            receive(364)
            if events[-1]["status"] != "CONFIRMED_DRIFT":
                raise RuntimeError("Recovered window did not confirm the positive control")
            result.update(success=True, recovery={
                "failed_input_offset": 242, "committed_after_failure": failed_offset,
                "retried_sequence": retried["sequence"], "retry_status": retried["status"],
                "recovered_last_status": events[-1]["status"], "event_count_total": len(events),
                "semantics": "at-least-once; window rewarm after restart",
            })
            result["success"] = False
            # 중복 입력은 조용히 계속 판정하지 않고 창을 다시 준비한다.
            send(True, 243)
            if producer.flush(20) or errors:
                raise RuntimeError("Duplicate-control delivery failed")
            receive(365)
            duplicate = events[-1]
            if (duplicate["status"] != "INSUFFICIENT_DATA"
                or duplicate["reason"] != "sequence_not_increasing"):
                raise RuntimeError("Duplicate sequence did not safely reset the window")
            for sequence in range(244, 365):
                send(True, sequence)
            if producer.flush(20) or errors:
                raise RuntimeError("Duplicate recovery input delivery failed")
            receive(486)
            if events[-1]["status"] != "CONFIRMED_DRIFT":
                raise RuntimeError("Window did not recover after duplicate input")
            for sequence, reason in ((366, "sequence_gap"), (365, "sequence_not_increasing")):
                send(True, sequence)
                if producer.flush(20) or errors:
                    raise RuntimeError("Ordering-control delivery failed")
                receive(len(events) + 1)
                if events[-1]["status"] != "INSUFFICIENT_DATA" or events[-1]["reason"] != reason:
                    raise RuntimeError("Gap/reordered sequence did not safely reset")
            if any(event["retraining_requested"] for event in events):
                raise RuntimeError("Recovery requested retraining unexpectedly")
            result.update(success=True, ordering={
                "duplicate_reset": duplicate["reason"], "recovery_status": "CONFIRMED_DRIFT",
                "gap_reset": "sequence_gap", "reordered_reset": "sequence_not_increasing",
                "event_count_total": len(events), "retraining_requests": 0,
            })
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
    parser.add_argument("--interval", type=float, default=0)
    parser.add_argument("--recovery", action="store_true")
    args = parser.parse_args()
    check(args.root, args.raw_dir, args.profile, args.docker, args.output, args.interval, args.recovery)
