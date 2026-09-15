"""TEP Kafka Sensor 메시지 생성 및 검증."""

from collections.abc import Mapping
from datetime import datetime
import math
from typing import Any


# ============================================================
# 1. Sensor Schema v1.0 기본 설정
# ============================================================

# Kafka 메시지 구조의 버전
SCHEMA_VERSION = "1.0"

# Kafka 메시지의 종류
EVENT_TYPE = "tep_sensor_reading"

# Id와 Time을 제외한 공정 변수 개수
EXPECTED_VALUE_COUNT = 56

# 기본 재생에 사용할 수 있는 공식 case
ALLOWED_CASES = {f"case{number}" for number in range(1, 7)}


# ============================================================
# 2. 숫자 변환 및 검사
# ============================================================

def _to_finite_float(value: Any, field_name: str) -> float:
    """
    CSV에서 읽은 값을 실수로 변환한다.

    숫자로 바꿀 수 없거나 NaN, 무한대인 경우 오류를 발생시킨다.
    """

    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{field_name} 값은 숫자여야 합니다: {value!r}"
        ) from exc

    # Kafka 메시지에 NaN이나 무한대가 들어가는 것을 방지한다.
    if not math.isfinite(converted):
        raise ValueError(
            f"{field_name} 값은 유한한 숫자여야 합니다: {value!r}"
        )

    return converted


# ============================================================
# 3. CSV 한 행을 Kafka 메시지로 변환
# ============================================================

def build_sensor_message(
    case_name: str,
    row: Mapping[str, Any],
    sequence: int,
    replayed_at: datetime | None = None,
) -> dict[str, Any]:
    """
    CSV 한 행을 Sensor Schema v1.0 형식으로 변환한다.

    예:
    case1.csv의 Id 17 데이터를
    trajectory_key가 case1::17인 Kafka 메시지로 만든다.
    """

    # case1부터 case6까지만 기본 재생 대상으로 허용한다.
    if case_name not in ALLOWED_CASES:
        raise ValueError(
            f"지원하지 않는 case입니다: {case_name}. "
            f"허용값: {sorted(ALLOWED_CASES)}"
        )

    # sequence는 첫 행 0부터 시작하여 한 행마다 1씩 증가한다.
    if isinstance(sequence, bool) or not isinstance(sequence, int):
        raise ValueError("sequence는 정수여야 합니다.")

    if sequence < 0:
        raise ValueError("sequence는 0 이상이어야 합니다.")

    # Kafka 메시지 생성에 필요한 Id와 Time이 있는지 확인한다.
    if "Id" not in row:
        raise ValueError("CSV 행에 Id 컬럼이 없습니다.")

    if "Time" not in row:
        raise ValueError("CSV 행에 Time 컬럼이 없습니다.")

    # Id를 정수로 변환한다.
    trajectory_id_value = _to_finite_float(row["Id"], "Id")

    if not trajectory_id_value.is_integer():
        raise ValueError(f"Id는 정수여야 합니다: {row['Id']!r}")

    trajectory_id = int(trajectory_id_value)

    # 원본 CSV의 Time을 시뮬레이션 시간으로 사용한다.
    timestamp_hours = _to_finite_float(row["Time"], "Time")

    if timestamp_hours < 0:
        raise ValueError("Time은 0 이상이어야 합니다.")

    # Id와 Time을 제외한 56개 공정 변수를 values에 저장한다.
    values = {
        column: _to_finite_float(value, column)
        for column, value in row.items()
        if column not in {"Id", "Time"}
    }

    # 공정 변수 개수가 데이터 설계와 일치하는지 확인한다.
    if len(values) != EXPECTED_VALUE_COUNT:
        raise ValueError(
            f"공정 변수는 {EXPECTED_VALUE_COUNT}개여야 하지만 "
            f"{len(values)}개가 확인됐습니다."
        )

    # 실제 Kafka 발행 시각을 생성한다.
    # 시간을 직접 전달하지 않으면 현재 컴퓨터 시간을 사용한다.
    actual_replayed_at = replayed_at or datetime.now().astimezone()

    # 실제 시각에는 +09:00 같은 시간대 정보가 필요하다.
    if actual_replayed_at.tzinfo is None:
        raise ValueError(
            "replayed_at에는 시간대 정보가 포함되어야 합니다."
        )

    # 최종 Sensor Schema v1.0 메시지를 생성한다.
    message = {
        "schema_version": SCHEMA_VERSION,
        "event_type": EVENT_TYPE,
        "trajectory_key": f"{case_name}::{trajectory_id}",
        "case": case_name,
        "trajectory_id": trajectory_id,
        "sequence": sequence,
        "timestamp_hours": timestamp_hours,
        "replayed_at": actual_replayed_at.isoformat(timespec="seconds"),
        "values": values,
    }

    # 생성된 메시지에 빠진 항목이나 잘못된 값이 없는지 검사한다.
    validate_sensor_message(message)

    return message


# ============================================================
# 4. 생성되거나 수신된 Kafka 메시지 검증
# ============================================================

def validate_sensor_message(message: Mapping[str, Any]) -> None:
    """
    Sensor Schema v1.0 메시지가 규칙에 맞는지 검사한다.

    문제가 없으면 아무것도 반환하지 않는다.
    문제가 있으면 ValueError를 발생시킨다.
    """

    # 메시지에 반드시 존재해야 하는 항목
    required_fields = {
        "schema_version",
        "event_type",
        "trajectory_key",
        "case",
        "trajectory_id",
        "sequence",
        "timestamp_hours",
        "replayed_at",
        "values",
    }

    # 빠진 필드가 있는지 확인한다.
    missing_fields = required_fields - set(message)

    if missing_fields:
        raise ValueError(
            f"필수 필드가 없습니다: {sorted(missing_fields)}"
        )

    # 메시지 버전 확인
    if message["schema_version"] != SCHEMA_VERSION:
        raise ValueError("지원하지 않는 schema_version입니다.")

    # 메시지 종류 확인
    if message["event_type"] != EVENT_TYPE:
        raise ValueError("지원하지 않는 event_type입니다.")

    # 공식 case인지 확인
    if message["case"] not in ALLOWED_CASES:
        raise ValueError(
            f"지원하지 않는 case입니다: {message['case']}"
        )

    # case와 Id로 만든 trajectory_key가 맞는지 확인한다.
    trajectory_id = message["trajectory_id"]
    expected_key = f"{message['case']}::{trajectory_id}"

    if message["trajectory_key"] != expected_key:
        raise ValueError(
            f"trajectory_key가 올바르지 않습니다: "
            f"{message['trajectory_key']!r}"
        )

    # 메시지 순번 확인
    sequence = message["sequence"]

    if isinstance(sequence, bool) or not isinstance(sequence, int):
        raise ValueError("sequence는 정수여야 합니다.")

    if sequence < 0:
        raise ValueError("sequence는 0 이상이어야 합니다.")

    # 시뮬레이션 시간이 정상적인 숫자인지 확인한다.
    timestamp_hours = _to_finite_float(
        message["timestamp_hours"],
        "timestamp_hours",
    )

    if timestamp_hours < 0:
        raise ValueError("timestamp_hours는 0 이상이어야 합니다.")

    # values가 객체 형태인지 확인한다.
    values = message["values"]

    if not isinstance(values, Mapping):
        raise ValueError("values는 객체 형식이어야 합니다.")

    # 공정 변수가 정확히 56개인지 확인한다.
    if len(values) != EXPECTED_VALUE_COUNT:
        raise ValueError(
            f"values에는 공정 변수 {EXPECTED_VALUE_COUNT}개가 필요합니다."
        )

    # Id와 Time은 values 안에 들어가면 안 된다.
    if "Id" in values or "Time" in values:
        raise ValueError(
            "values에는 Id와 Time이 포함되면 안 됩니다."
        )

    # 56개 공정 변수가 모두 정상적인 숫자인지 확인한다.
    for column, value in values.items():
        _to_finite_float(value, column)

    # 실제 전송 시각이 ISO 8601 형식인지 확인한다.
    try:
        parsed_time = datetime.fromisoformat(
            str(message["replayed_at"])
        )
    except ValueError as exc:
        raise ValueError(
            "replayed_at이 올바른 ISO 8601 형식이 아닙니다."
        ) from exc

    # 실제 전송 시각에 시간대가 포함됐는지 확인한다.
    if parsed_time.tzinfo is None:
        raise ValueError(
            "replayed_at에는 시간대 정보가 포함되어야 합니다."
        )