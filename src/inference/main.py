"""Kafka 수신부터 Prediction 발행까지 전체 과정을 실행하는 메인 파일.

입력 토픽: tep-sensor-data
처리 순서: 센서 수신 → 60분 버퍼 → 728개 Feature → 모델 4개 추론
출력 토픽: tep-predictions

사용자는 프로젝트 루트에서 ``python -m src.inference.main``만 실행하면 된다.
"""

from __future__ import annotations

import json
import os
import signal
from pathlib import Path

from confluent_kafka import Consumer, KafkaError, Producer
from dotenv import load_dotenv

from kafka.message_schema import validate_sensor_message

from .model_loader import ProductionPredictor
from .temporal_features import TrajectoryFeatureBuffer


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
RUNNING = True


def _stop(_signum, _frame) -> None:
    """Ctrl+C를 받으면 현재 처리를 마친 뒤 안전하게 반복문을 종료한다."""
    global RUNNING
    RUNNING = False


def decode_sensor_message(kafka_message) -> dict:
    """Decode and validate a Kafka sensor message, including its key."""
    raw_value = kafka_message.value()
    if raw_value is None:
        raise ValueError("Kafka message value가 없습니다.")
    sensor = json.loads(raw_value.decode("utf-8"))
    if not isinstance(sensor, dict):
        raise ValueError("Sensor 메시지는 JSON 객체여야 합니다.")
    validate_sensor_message(sensor)

    raw_key = kafka_message.key()
    if raw_key is None:
        raise ValueError("Kafka message key가 없습니다.")
    kafka_key = raw_key.decode("utf-8")
    if kafka_key != sensor["trajectory_key"]:
        raise ValueError(
            f"Kafka key 불일치: {kafka_key!r} != {sensor['trajectory_key']!r}"
        )
    return sensor


def main() -> None:
    """환경설정을 읽고 Kafka 실시간 추론 서비스를 계속 실행한다."""

    # .env에 값이 있으면 사용하고, 없으면 오른쪽 기본값을 사용한다.
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    sensor_topic = os.getenv("KAFKA_SENSOR_TOPIC", "tep-sensor-data")
    prediction_topic = os.getenv("KAFKA_PREDICTION_TOPIC", "tep-predictions")
    consumer_group = os.getenv("KAFKA_CONSUMER_GROUP", "inference-service")
    model_dir = Path(os.getenv(
        "MODEL_DIR", str(PROJECT_ROOT / "models" / "production" / "v1.0.0")
    ))

    # 서비스 시작 시 모델을 로딩하고 trajectory별 메모리 버퍼를 준비한다.
    predictor = ProductionPredictor(model_dir)
    buffer = TrajectoryFeatureBuffer(predictor.features)
    # Sensor Consumer: 아직 처리하지 않은 센서 메시지를 읽는다.
    # 자동 커밋을 끄고 정상 처리 후에만 아래에서 직접 커밋한다.
    consumer = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": consumer_group,
        "auto.offset.reset": "latest",
        "enable.auto.commit": False,
    })
    # Prediction Producer: 추론 결과를 출력 토픽으로 보낸다.
    producer = Producer({
        "bootstrap.servers": bootstrap,
        "client.id": "tep-inference-producer",
        "acks": "all",
        "enable.idempotence": True,
        "message.timeout.ms": 10000,
    })

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    consumer.subscribe([sensor_topic])
    print(f"Kafka 서버: {bootstrap}")
    print(f"입력 토픽: {sensor_topic}")
    print(f"출력 토픽: {prediction_topic}")
    print("[수신 대기] Producer를 실행하세요. 첫 20개 메시지는 60분 준비 구간입니다.")

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
                # 1) Kafka JSON, Sensor schema와 message key를 검사한다.
                sensor = decode_sensor_message(kafka_message)
                # 2) 해당 trajectory의 최근 60분 버퍼에 센서 한 행을 추가한다.
                buffered = buffer.add(sensor)
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
                # Skip only the bad input so it cannot stop the service repeatedly.
                print(f"[입력 오류] offset={kafka_message.offset()}: {error}")
                consumer.commit(message=kafka_message, asynchronous=False)
                continue
            if not buffered.ready:
                # 최초 20개는 계산에 필요한 과거 데이터이므로 예측하지 않는다.
                print(
                    f"[준비 중] {buffered.trajectory_key} "
                    f"{buffered.buffered_rows}/21"
                )
                consumer.commit(message=kafka_message, asynchronous=False)
                continue

            # 3) 21개가 모였으면 728개 Feature로 모델 추론을 실행한다.
            prediction = predictor.predict(
                buffered.features,
                buffered.trajectory_key,
                buffered.timestamp_hours,
            )
            # 4) 결과를 tep-predictions 토픽에 JSON으로 발행한다.
            producer.produce(
                topic=prediction_topic,
                key=buffered.trajectory_key.encode("utf-8"),
                value=json.dumps(
                    prediction, ensure_ascii=False, allow_nan=False
                ).encode("utf-8"),
            )
            if producer.flush(10) != 0:
                raise RuntimeError("Prediction 메시지 발행 제한 시간을 초과했습니다.")
            # 5) Prediction 발행까지 성공한 Sensor 메시지만 처리 완료로 기록한다.
            consumer.commit(message=kafka_message, asynchronous=False)
            print(
                f"[추론 완료] {buffered.trajectory_key} "
                f"sequence={buffered.sequence}, "
                f"time={buffered.timestamp_hours}, "
                f"status={prediction['status']}, "
                f"rul={prediction['rul']['hours']:.3f}h"
            )
    finally:
        # 정상 종료와 오류 종료 모두 Kafka 연결을 정리한다.
        consumer.close()
        producer.flush(10)
        print("실시간 추론 서비스를 종료했습니다.")


if __name__ == "__main__":
    main()
