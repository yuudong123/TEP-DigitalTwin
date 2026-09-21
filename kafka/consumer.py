"""TEP Kafka Sensor 메시지 확인용 Consumer."""

import argparse
import json
import os
import time
from pathlib import Path

from confluent_kafka import Consumer, KafkaError, KafkaException
from dotenv import load_dotenv

try:
    from .message_schema import validate_sensor_message
    from .topic_admin import ensure_topic
except ImportError:
    from message_schema import validate_sensor_message
    from topic_admin import ensure_topic


# ============================================================
# 1. 프로젝트 경로와 환경변수
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 프로젝트 루트의 .env 파일을 읽는다.
load_dotenv(PROJECT_ROOT / ".env")


# ============================================================
# 2. Kafka 메시지 수신 및 검증
# ============================================================

def consume_messages(
    case_name: str,
    trajectory_id: int,
    expected_count: int | None,
    idle_timeout: float,
):
    """선택한 trajectory의 Kafka 메시지를 수신하고 검증한다."""

    bootstrap_servers = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        "localhost:9092",
    )

    topic = os.getenv(
        "KAFKA_SENSOR_TOPIC",
        "tep-sensor-data",
    )

    topic_created = ensure_topic(bootstrap_servers, topic)

    # 추론 서비스와 메시지를 나눠 갖지 않도록
    # 확인용 Consumer는 별도 그룹을 사용한다.
    base_group_id = os.getenv(
        "KAFKA_CHECK_CONSUMER_GROUP",
        "tep-replay-check",
    )

    # 실행할 때마다 새로운 그룹을 만들어
    # 이전 실행의 offset 영향을 받지 않게 한다.
    group_id = f"{base_group_id}-{int(time.time())}"

    target_key = f"{case_name}::{trajectory_id}"

    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,

            # Consumer 실행 이후 들어오는 메시지만 받는다.
            "auto.offset.reset": "latest",

            # 확인용이므로 offset을 자동 저장하지 않는다.
            "enable.auto.commit": False,
        }
    )

    consumer.subscribe([topic])

    received_count = 0
    schema_valid_count = 0
    sequence_error_count = 0
    message_error_count = 0

    # 첫 메시지는 sequence=0이어야 한다.
    expected_sequence = 0

    # 마지막 대상 메시지를 받은 시각
    last_received_at = time.monotonic()

    print(f"Kafka 서버: {bootstrap_servers}")
    print(f"Kafka 토픽: {topic}")
    print(
        "Kafka 토픽 준비: "
        f"{'새로 생성' if topic_created else '기존 토픽 사용'}"
    )
    print(f"Consumer 그룹: {group_id}")
    print(f"확인 trajectory: {target_key}")

    if expected_count is None:
        print("예상 수신 개수: 지정하지 않음")
    else:
        print(f"예상 수신 개수: {expected_count}")

    print()
    print("[수신 대기] 이제 다른 PowerShell에서 Producer를 실행하세요.")
    print("중간에 종료하려면 Ctrl+C를 누르세요.")
    print()

    try:
        while True:
            kafka_message = consumer.poll(timeout=1.0)

            # 1초 동안 들어온 메시지가 없는 경우
            if kafka_message is None:
                waiting_seconds = (
                    time.monotonic() - last_received_at
                )

                if waiting_seconds >= idle_timeout:
                    print(
                        f"[대기 종료] {idle_timeout}초 동안 "
                        f"대상 메시지가 들어오지 않았습니다."
                    )
                    break

                continue

            # Kafka 자체 오류 확인
            if kafka_message.error():
                if (
                    kafka_message.error().code()
                    == KafkaError._PARTITION_EOF
                ):
                    continue

                raise KafkaException(kafka_message.error())

            try:
                # Kafka value를 JSON 객체로 변환한다.
                message = json.loads(
                    kafka_message.value().decode("utf-8")
                )
            except (
                UnicodeDecodeError,
                json.JSONDecodeError,
                AttributeError,
            ) as error:
                message_error_count += 1
                print(f"[JSON 오류] {error}")
                continue

            # 현재 확인할 trajectory가 아니면 건너뛴다.
            if message.get("trajectory_key") != target_key:
                continue

            received_count += 1
            last_received_at = time.monotonic()

            try:
                # message_schema.py의 규칙으로 메시지를 검증한다.
                validate_sensor_message(message)

                # Kafka message key와 JSON 내부 key가 같은지 확인한다.
                raw_kafka_key = kafka_message.key()

                if raw_kafka_key is None:
                    raise ValueError("Kafka message key가 없습니다.")

                kafka_key = raw_kafka_key.decode("utf-8")

                if kafka_key != target_key:
                    raise ValueError(
                        f"Kafka key 불일치: "
                        f"{kafka_key!r} != {target_key!r}"
                    )

                schema_valid_count += 1

            except (
                ValueError,
                UnicodeDecodeError,
                TypeError,
            ) as error:
                message_error_count += 1
                print(
                    f"[메시지 오류] "
                    f"수신 순번={received_count}, "
                    f"내용={error}"
                )

            # sequence가 0부터 연속으로 증가하는지 확인한다.
            sequence = message.get("sequence")

            if sequence != expected_sequence:
                sequence_error_count += 1

                print(
                    f"[순서 오류] 예상={expected_sequence}, "
                    f"실제={sequence}"
                )

                # 이후 메시지는 실제 sequence 다음부터 검사한다.
                if isinstance(sequence, int):
                    expected_sequence = sequence + 1
            else:
                expected_sequence += 1

            # 첫 메시지, 100개 단위, 마지막 메시지 출력
            if (
                received_count == 1
                or received_count % 100 == 0
                or received_count == expected_count
            ):
                print(
                    f"[수신 진행] {received_count}"
                    f"{f'/{expected_count}' if expected_count else ''}, "
                    f"sequence={sequence}, "
                    f"time={message.get('timestamp_hours')}"
                )

            # 예상 개수를 모두 받으면 자동 종료한다.
            if (
                expected_count is not None
                and received_count >= expected_count
            ):
                break

    except KeyboardInterrupt:
        print()
        print("[사용자 종료] Consumer 수신을 중단합니다.")

    finally:
        consumer.close()

    # ========================================================
    # 3. 최종 검증 결과
    # ========================================================

    print()
    print("========== Consumer 검증 결과 ==========")
    print(f"trajectory: {target_key}")
    print(f"수신 메시지: {received_count}")
    print(f"스키마 정상: {schema_valid_count}")
    print(f"메시지 오류: {message_error_count}")
    print(f"sequence 오류: {sequence_error_count}")

    count_matches = (
        expected_count is None
        or received_count == expected_count
    )

    if (
        count_matches
        and message_error_count == 0
        and sequence_error_count == 0
    ):
        print("최종 결과: 정상")
    else:
        print("최종 결과: 확인 필요")


# ============================================================
# 4. 명령어 실행
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="TEP Kafka Sensor 확인용 Consumer"
    )

    parser.add_argument(
        "--case",
        required=True,
        choices=[f"case{number}" for number in range(1, 7)],
        help="확인할 case 이름",
    )

    parser.add_argument(
        "--id",
        required=True,
        type=int,
        dest="trajectory_id",
        help="확인할 trajectory Id",
    )

    parser.add_argument(
        "--expected-count",
        type=int,
        default=None,
        help="Producer가 보낼 것으로 예상되는 메시지 개수",
    )

    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=60.0,
        help="메시지가 없을 때 수신을 종료할 대기시간(초)",
    )

    args = parser.parse_args()

    if args.trajectory_id < 1:
        raise ValueError("Id는 1 이상이어야 합니다.")

    if (
        args.expected_count is not None
        and args.expected_count < 1
    ):
        raise ValueError("expected-count는 1 이상이어야 합니다.")

    if args.idle_timeout <= 0:
        raise ValueError("idle-timeout은 0보다 커야 합니다.")

    consume_messages(
        case_name=args.case,
        trajectory_id=args.trajectory_id,
        expected_count=args.expected_count,
        idle_timeout=args.idle_timeout,
    )


if __name__ == "__main__":
    main()
