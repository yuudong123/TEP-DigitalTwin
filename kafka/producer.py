"""TEP trajectory를 Kafka로 재생하는 Producer."""

import argparse
import csv
import json
import os
import time
from functools import partial
from pathlib import Path

from confluent_kafka import Producer
from dotenv import load_dotenv

try:
    from .message_schema import build_sensor_message
    from .topic_admin import ensure_topic
except ImportError:
    from message_schema import build_sensor_message
    from topic_admin import ensure_topic


# ============================================================
# 1. 프로젝트 경로와 환경변수
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 프로젝트 루트의 .env 파일을 읽는다.
load_dotenv(PROJECT_ROOT / ".env")


def get_data_raw_dir() -> Path:
    """환경변수의 데이터 경로를 프로젝트 기준 절대 경로로 바꾼다."""

    configured_path = Path(
        os.getenv("DATA_RAW_DIR", "data/raw/TEP")
    )

    if configured_path.is_absolute():
        return configured_path

    return PROJECT_ROOT / configured_path


def resolve_case_csv_path(case_name: str) -> Path:
    """현재 경로와 기존 data/raw 설정을 모두 지원한다."""

    data_raw_dir = get_data_raw_dir()
    direct_path = data_raw_dir / f"{case_name}.csv"

    if direct_path.exists():
        return direct_path

    nested_path = data_raw_dir / "TEP" / f"{case_name}.csv"

    if nested_path.exists():
        return nested_path

    return direct_path


# ============================================================
# 2. 선택한 trajectory 불러오기
# ============================================================

def load_trajectory(case_name: str, trajectory_id: int):
    """
    선택한 case와 Id의 데이터만 가져온 뒤
    Time 오름차순으로 정렬한다.
    """

    csv_path = resolve_case_csv_path(case_name)

    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV 파일을 찾을 수 없습니다: {csv_path}"
        )

    selected_rows = []

    # 대용량 CSV를 한 행씩 읽는다.
    with csv_path.open(
        mode="r",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:
        reader = csv.DictReader(csv_file)

        for row in reader:
            row_id = int(float(row["Id"]))

            if row_id == trajectory_id:
                selected_rows.append(row)

    if not selected_rows:
        raise ValueError(
            f"{case_name}에서 Id={trajectory_id} 데이터를 찾지 못했습니다."
        )

    selected_rows.sort(key=lambda row: float(row["Time"]))

    return selected_rows


# ============================================================
# 3. Kafka 없이 메시지 생성 결과 확인
# ============================================================

def preview_messages(
    case_name: str,
    rows: list[dict],
    limit: int,
):
    """Kafka에 전송하지 않고 일부 메시지만 화면에 출력한다."""

    print(f"미리보기 메시지 개수: {min(limit, len(rows))}")
    print()

    for sequence, row in enumerate(rows[:limit]):
        message = build_sensor_message(
            case_name=case_name,
            row=row,
            sequence=sequence,
        )

        print(
            f"sequence={message['sequence']}, "
            f"time={message['timestamp_hours']}, "
            f"key={message['trajectory_key']}, "
            f"values={len(message['values'])}"
        )


# ============================================================
# 4. Kafka 전송 결과 처리
# ============================================================

def delivery_report(error, kafka_message, delivery_counts):
    """
    Kafka가 메시지 전송 결과를 알려줄 때 실행된다.

    성공·실패 횟수를 각각 기록하고,
    실패한 경우 오류를 화면에 출력한다.
    """

    if error is not None:
        delivery_counts["failure"] += 1
        print(f"[전송 실패] {error}")
    else:
        delivery_counts["success"] += 1


# ============================================================
# 5. 선택한 trajectory를 Kafka로 전송
# ============================================================

def publish_trajectory(
    case_name: str,
    rows: list[dict],
    interval_seconds: float,
):
    """선택한 trajectory 전체를 Kafka로 순차 전송한다."""

    bootstrap_servers = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        "localhost:9092",
    )

    topic = os.getenv(
        "KAFKA_SENSOR_TOPIC",
        "tep-sensor-data",
    )

    topic_created = ensure_topic(bootstrap_servers, topic)

    # Kafka Producer 생성
    producer = Producer(
        {
            "bootstrap.servers": bootstrap_servers,
            "client.id": "tep-replay-producer",
            "acks": "all",
            "enable.idempotence": True,
            "message.timeout.ms": 10000,
        }
    )

    print(f"Kafka 서버: {bootstrap_servers}")
    print(f"Kafka 토픽: {topic}")
    print(
        "Kafka 토픽 준비: "
        f"{'새로 생성' if topic_created else '기존 토픽 사용'}"
    )
    print(f"전송 간격: {interval_seconds}초")
    print(f"전송 예정: {len(rows)}개")
    print()

    # produce() 호출 횟수가 아니라 Kafka broker가 확인한 실제 전송 결과를
    # delivery callback에서 집계한다.
    delivery_counts = {
        "success": 0,
        "failure": 0,
    }

    # confluent-kafka가 callback을 호출할 때 위 집계 객체도 함께 전달한다.
    delivery_callback = partial(
        delivery_report,
        delivery_counts=delivery_counts,
    )

    for sequence, row in enumerate(rows):
        message = build_sensor_message(
            case_name=case_name,
            row=row,
            sequence=sequence,
        )

        # 메시지 key와 value를 UTF-8 바이트로 변환한다.
        message_key = message["trajectory_key"].encode("utf-8")

        message_value = json.dumps(
            message,
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

        # 내부 전송 대기열이 가득 찬 경우 poll 후 다시 시도한다.
        while True:
            try:
                producer.produce(
                    topic=topic,
                    key=message_key,
                    value=message_value,
                    on_delivery=delivery_callback,
                )
                break
            except BufferError:
                producer.poll(1)

        # 전송 완료·실패 콜백을 처리한다.
        producer.poll(0)

        sent_count = sequence + 1

        # 첫 메시지, 100개 단위, 마지막 메시지에서 진행률 출력
        if (
            sent_count == 1
            or sent_count % 100 == 0
            or sent_count == len(rows)
        ):
            print(
                f"[전송 진행] {sent_count}/{len(rows)} "
                f"sequence={sequence}, "
                f"time={message['timestamp_hours']}"
            )

        # 마지막 메시지 뒤에는 대기하지 않는다.
        if sent_count < len(rows):
            time.sleep(interval_seconds)

    # 전송 대기열의 메시지가 모두 처리될 때까지 기다린다.
    remaining_count = producer.flush(30)

    requested_count = len(rows)
    success_count = delivery_counts["success"]

    # callback에서 실패한 메시지와 flush 제한 시간 안에 처리되지 않은
    # 메시지를 모두 최종 실패 건수에 포함한다.
    failure_count = delivery_counts["failure"] + remaining_count

    print()
    print("========== Producer 전송 결과 ==========")
    print(f"전송 요청: {requested_count}")
    print(f"전송 성공: {success_count}")
    print(f"전송 실패: {failure_count}")

    if (
        success_count == requested_count
        and failure_count == 0
    ):
        print("최종 결과: 정상")
        return

    print("최종 결과: 실패")

    if remaining_count > 0:
        print(
            f"제한 시간 안에 처리되지 않은 메시지: "
            f"{remaining_count}"
        )

    raise RuntimeError(
        "일부 Kafka 메시지가 정상적으로 전송되지 않았습니다."
    )


# ============================================================
# 6. 명령어 실행
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="TEP trajectory Kafka 재생 Producer"
    )

    parser.add_argument(
        "--case",
        required=True,
        choices=[f"case{number}" for number in range(1, 7)],
        help="재생할 case 이름",
    )

    parser.add_argument(
        "--id",
        required=True,
        type=int,
        dest="trajectory_id",
        help="재생할 trajectory Id",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="미리보기에서 출력할 메시지 개수",
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=float(
            os.getenv("TEP_REPLAY_INTERVAL_SECONDS", "0.1")
        ),
        help="Kafka 메시지 전송 간격(초)",
    )

    parser.add_argument(
        "--send",
        action="store_true",
        help="이 옵션을 넣었을 때만 Kafka로 실제 전송",
    )

    args = parser.parse_args()

    if args.trajectory_id < 1:
        raise ValueError("Id는 1 이상이어야 합니다.")

    if args.limit < 1:
        raise ValueError("limit은 1 이상이어야 합니다.")

    if args.interval < 0:
        raise ValueError("interval은 0 이상이어야 합니다.")

    rows = load_trajectory(
        case_name=args.case,
        trajectory_id=args.trajectory_id,
    )

    print(f"선택 trajectory: {args.case}::{args.trajectory_id}")
    print(f"전체 행 개수: {len(rows)}")
    print(f"첫 Time: {rows[0]['Time']}")
    print(f"마지막 Time: {rows[-1]['Time']}")
    print()

    if args.send:
        publish_trajectory(
            case_name=args.case,
            rows=rows,
            interval_seconds=args.interval,
        )
    else:
        print("[미리보기 모드] Kafka로 전송하지 않습니다.")
        print("실제 전송하려면 --send 옵션을 추가하세요.")
        print()

        preview_messages(
            case_name=args.case,
            rows=rows,
            limit=args.limit,
        )


if __name__ == "__main__":
    main()
