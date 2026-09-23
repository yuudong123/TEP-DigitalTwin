"""Kafka Sensor 메시지에서 TEP 운전상태·열화 변화를 발행하는 모듈."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import signal
import time
from typing import Any, Mapping

from confluent_kafka import Consumer, KafkaError, Producer
from dotenv import load_dotenv

from kafka.message_schema import validate_sensor_message
from kafka.topic_admin import ensure_topic

from .drift_detector import DriftDetector, DriftResult, DriftThresholds
from .event_schema import build_drift_event
from .retraining_trigger import RetrainingTrigger
from .window_manager import SlidingWindowManager, WindowUpdate


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
RUNNING = True


@dataclass(frozen=True)
class MonitorSettings:
    bootstrap_servers: str
    sensor_topic: str
    drift_topic: str
    consumer_group: str
    reference_path: Path
    reference_version: str
    model_version: str
    check_interval_seconds: float
    minimum_timestamp_hours: float
    retraining_enabled: bool
    retraining_state_path: Path


def settings_from_environment() -> MonitorSettings:
    def boolean(name: str, default: bool) -> bool:
        return os.getenv(name, str(default)).strip().lower() in {
            "1", "true", "yes", "on"
        }

    def path(name: str, default: Path) -> Path:
        configured = Path(os.getenv(name, str(default)))
        return configured if configured.is_absolute() else PROJECT_ROOT / configured

    return MonitorSettings(
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        sensor_topic=os.getenv("KAFKA_SENSOR_TOPIC", "tep-sensor-data"),
        drift_topic=os.getenv("KAFKA_DRIFT_TOPIC", "tep-drift-events"),
        consumer_group=os.getenv("DRIFT_CONSUMER_GROUP", "drift-monitor"),
        reference_path=path(
            "DRIFT_REFERENCE_PATH",
            PROJECT_ROOT / "models" / "monitoring" / "drift-reference-v1.0.0.json",
        ),
        reference_version=os.getenv("DRIFT_REFERENCE_VERSION", "v1.0.0"),
        model_version=os.getenv("MODEL_VERSION", "v1.0.0"),
        check_interval_seconds=float(
            os.getenv("DRIFT_CHECK_INTERVAL_SECONDS", "60")
        ),
        minimum_timestamp_hours=float(
            os.getenv("DRIFT_MIN_TIMESTAMP_HOURS", "30")
        ),
        # 현재 TEP 데이터에는 운영 Drift label이 없으므로 자동 재학습은 기본 차단한다.
        retraining_enabled=boolean("RETRAIN_ENABLED", False),
        retraining_state_path=path(
            "DRIFT_RETRAINING_STATE_PATH",
            PROJECT_ROOT / "logs" / "retraining-state.json",
        ),
    )


def load_reference(path: Path) -> tuple[str, dict[str, dict[str, list[float]]]]:
    if not path.exists():
        raise FileNotFoundError(f"Drift 기준 분포를 찾을 수 없습니다: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features")
    cases = payload.get("cases")
    version = payload.get("reference_version")
    if not isinstance(features, list) or len(features) != 52:
        raise ValueError("Drift 기준 분포의 Feature는 52개여야 합니다.")
    if not isinstance(cases, dict) or not cases:
        raise ValueError("Drift 기준 분포에 case가 없습니다.")

    result: dict[str, dict[str, list[float]]] = {}
    for case_name, case_payload in cases.items():
        feature_payload = case_payload.get("features", {})
        current: dict[str, list[float]] = {}
        for feature in features:
            sample = feature_payload.get(feature, {}).get("reference_sample")
            if not isinstance(sample, list) or len(sample) < 20:
                raise ValueError(f"{case_name} 기준 표본이 부족합니다: {feature}")
            current[feature] = [float(value) for value in sample]
        result[case_name] = current
    return str(version), result


def decode_sensor_message(kafka_message: Any) -> dict[str, Any]:
    raw_value = kafka_message.value()
    if raw_value is None:
        raise ValueError("Kafka message value가 없습니다.")
    message = json.loads(raw_value.decode("utf-8"))
    if not isinstance(message, dict):
        raise ValueError("Sensor 메시지는 JSON 객체여야 합니다.")
    validate_sensor_message(message)
    raw_key = kafka_message.key()
    if raw_key is None:
        raise ValueError("Kafka message key가 없습니다.")
    kafka_key = raw_key.decode("utf-8")
    if kafka_key != message["trajectory_key"]:
        raise ValueError("Kafka key와 trajectory_key가 다릅니다.")
    return message


class DriftMonitor:
    def __init__(
        self,
        *,
        features: list[str],
        references: Mapping[str, Mapping[str, list[float]]],
        reference_version: str,
        model_version: str,
        check_interval_seconds: float = 60.0,
        minimum_timestamp_hours: float = 30.0,
        retraining_enabled: bool = False,
        retraining_state_path: Path = Path("retraining-state.json"),
        window_size: int = 120,
        min_samples: int = 20,
        thresholds: DriftThresholds | None = None,
        clock: Any = time.monotonic,
    ) -> None:
        if check_interval_seconds < 0:
            raise ValueError("check_interval_seconds는 0 이상이어야 합니다.")
        if minimum_timestamp_hours < 0:
            raise ValueError("minimum_timestamp_hours는 0 이상이어야 합니다.")
        self.features = features
        self.references = references
        self.reference_version = reference_version
        self.model_version = model_version
        self.check_interval_seconds = check_interval_seconds
        self.minimum_timestamp_hours = minimum_timestamp_hours
        self.clock = clock
        self.window = SlidingWindowManager(features, window_size, min_samples)
        # 연속 Drift 횟수는 case가 아니라 trajectory별 상태다. 같은 case의
        # 여러 trajectory를 번갈아 처리해도 서로의 확인 횟수가 섞이지 않아야 한다.
        self.detectors: dict[str, DriftDetector] = {}
        self.thresholds = thresholds
        self.trigger = RetrainingTrigger(
            retraining_state_path,
            enabled=retraining_enabled,
            clock=lambda: datetime.now().astimezone(),
        )
        self.last_checked_at: dict[str, float] = {}

    def process(self, message: Mapping[str, Any]) -> dict[str, Any] | None:
        case_name = str(message["case"])
        trajectory_key = str(message["trajectory_key"])
        if case_name not in self.references:
            raise ValueError(f"기준 분포가 없는 case입니다: {case_name}")

        update = self.window.add(message)
        detector = self.detectors.setdefault(
            trajectory_key, DriftDetector(self.thresholds)
        )
        if update.reset_reason:
            detector.reset()

        if update.timestamp_hours < self.minimum_timestamp_hours:
            event = self._event(
                message,
                update,
                DriftResult(
                    status="INSUFFICIENT_DATA",
                    drifted_feature_count=0,
                    monitored_feature_count=len(self.features),
                    drifted_feature_ratio=0.0,
                    consecutive_drift_count=0,
                    features=[],
                ),
                False,
                "before_reference_window",
            )
            # 기준 시작 이전 샘플은 이후 판정 창에 섞이면 안 된다.
            self.window.remove(trajectory_key)
            self.detectors.pop(trajectory_key, None)
            self.last_checked_at.pop(trajectory_key, None)
            return event

        if not update.ready:
            result = DriftResult(
                status="INSUFFICIENT_DATA",
                drifted_feature_count=0,
                monitored_feature_count=len(self.features),
                drifted_feature_ratio=0.0,
                consecutive_drift_count=0,
                features=[],
            )
            reason = update.reset_reason or "window_warmup"
            return self._event(message, update, result, False, reason)

        now = self.clock()
        previous = self.last_checked_at.get(trajectory_key)
        if (
            previous is not None
            and self.check_interval_seconds > 0
            and now - previous < self.check_interval_seconds
        ):
            return None
        self.last_checked_at[trajectory_key] = now

        result = detector.detect(
            self.references[case_name],
            self.window.current(trajectory_key),
        )
        decision = self.trigger.evaluate(
            case_name=case_name,
            drift_status=result.status,
            quality_valid=True,
        )
        reason = decision.reason if decision.requested else ""
        return self._event(
            message,
            update,
            result,
            decision.requested,
            reason,
        )

    def _event(
        self,
        message: Mapping[str, Any],
        update: WindowUpdate,
        result: DriftResult,
        retraining_requested: bool,
        reason: str,
    ) -> dict[str, Any]:
        start, end = self.window.bounds(update.trajectory_key)
        return build_drift_event(
            trajectory_key=update.trajectory_key,
            case_name=update.case_name,
            sequence=update.sequence,
            timestamp_hours=update.timestamp_hours,
            reference_version=self.reference_version,
            model_version=self.model_version,
            window_start=start,
            window_end=end,
            window_samples=update.sample_count,
            result=result,
            retraining_requested=retraining_requested,
            reason=reason,
        )


def _stop(_signum: int, _frame: Any) -> None:
    global RUNNING
    RUNNING = False


def main() -> None:
    settings = settings_from_environment()
    reference_version, references = load_reference(settings.reference_path)
    features = list(next(iter(references.values())).keys())
    ensure_topic(settings.bootstrap_servers, settings.drift_topic)

    monitor = DriftMonitor(
        features=features,
        references=references,
        reference_version=reference_version,
        model_version=settings.model_version,
        check_interval_seconds=settings.check_interval_seconds,
        minimum_timestamp_hours=settings.minimum_timestamp_hours,
        retraining_enabled=settings.retraining_enabled,
        retraining_state_path=settings.retraining_state_path,
    )
    consumer = Consumer({
        "bootstrap.servers": settings.bootstrap_servers,
        "group.id": settings.consumer_group,
        "auto.offset.reset": "latest",
        "enable.auto.commit": False,
    })
    producer = Producer({
        "bootstrap.servers": settings.bootstrap_servers,
        "client.id": "tep-drift-monitor",
        "acks": "all",
        "enable.idempotence": True,
        "message.timeout.ms": 10000,
    })
    consumer.subscribe([settings.sensor_topic])
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    print(f"Kafka 서버: {settings.bootstrap_servers}")
    print(f"입력 토픽: {settings.sensor_topic}")
    print(f"출력 토픽: {settings.drift_topic}")
    print(f"기준 분포: {settings.reference_path}")
    print("[수신 대기] Sensor 메시지를 기다립니다.")

    try:
        while RUNNING:
            kafka_message = consumer.poll(1.0)
            if kafka_message is None:
                continue
            if kafka_message.error():
                if kafka_message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise RuntimeError(kafka_message.error())
            try:
                message = decode_sensor_message(kafka_message)
                event = monitor.process(message)
                if event is not None:
                    producer.produce(
                        settings.drift_topic,
                        key=message["trajectory_key"].encode("utf-8"),
                        value=json.dumps(
                            event, ensure_ascii=False, allow_nan=False
                        ).encode("utf-8"),
                    )
                    if producer.flush(10) != 0:
                        raise RuntimeError("Drift Event 발행 제한 시간을 초과했습니다.")
                    print(
                        f"[Drift Event] {message['trajectory_key']} "
                        f"sequence={message['sequence']} status={event['status']}"
                    )
                consumer.commit(message=kafka_message, asynchronous=False)
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
                print(f"[입력 오류] offset={kafka_message.offset()}: {error}")
                consumer.commit(message=kafka_message, asynchronous=False)
    finally:
        consumer.close()
        producer.flush(10)
        print("Drift Monitor를 종료했습니다.")


if __name__ == "__main__":
    main()
