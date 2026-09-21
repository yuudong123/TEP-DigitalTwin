from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
from typing import Any, Mapping


@dataclass(frozen=True)
class WindowUpdate:
    trajectory_key: str
    case_name: str
    sequence: int
    timestamp_hours: float
    sample_count: int
    ready: bool
    reset_reason: str | None


@dataclass
class _TrajectoryState:
    case_name: str
    rows: deque[dict[str, float]]
    last_sequence: int | None = None
    last_timestamp_hours: float | None = None


class SlidingWindowManager:
    """Trajectory별 최근 센서 관측값을 독립적으로 유지한다."""

    def __init__(
        self,
        features: list[str],
        window_size: int = 120,
        min_samples: int = 20,
    ) -> None:
        if not features or len(features) != len(set(features)):
            raise ValueError("감시 Feature는 중복 없이 한 개 이상이어야 합니다.")
        if window_size < 1:
            raise ValueError("window_size는 1 이상이어야 합니다.")
        if not 1 <= min_samples <= window_size:
            raise ValueError("min_samples는 1 이상 window_size 이하여야 합니다.")

        self.features = tuple(features)
        self.window_size = window_size
        self.min_samples = min_samples
        self._states: dict[str, _TrajectoryState] = {}

    def add(self, message: Mapping[str, Any]) -> WindowUpdate:
        trajectory_key = self._required_string(message, "trajectory_key")
        case_name = self._required_string(message, "case")
        trajectory_id = self._required_integer(message, "trajectory_id")
        sequence = self._required_integer(message, "sequence")
        timestamp_hours = self._required_finite_number(message, "timestamp_hours")
        values = message.get("values")
        if not isinstance(values, Mapping):
            raise ValueError("values는 객체여야 합니다.")

        expected_key = f"{case_name}::{trajectory_id}"
        if trajectory_key != expected_key:
            raise ValueError(
                f"trajectory_key가 case와 trajectory_id에 맞지 않습니다: {trajectory_key}"
            )

        row = {}
        for feature in self.features:
            if feature not in values:
                raise ValueError(f"감시 Feature가 없습니다: {feature}")
            row[feature] = self._finite_value(values[feature], feature)

        state = self._states.get(trajectory_key)
        if state is None:
            state = self._new_state(case_name)
            self._states[trajectory_key] = state

        reset_reason = self._discontinuity_reason(
            state,
            case_name,
            sequence,
            timestamp_hours,
        )
        if reset_reason is not None:
            state = self._new_state(case_name)
            self._states[trajectory_key] = state

        state.rows.append(row)
        state.last_sequence = sequence
        state.last_timestamp_hours = timestamp_hours
        sample_count = len(state.rows)
        return WindowUpdate(
            trajectory_key=trajectory_key,
            case_name=case_name,
            sequence=sequence,
            timestamp_hours=timestamp_hours,
            sample_count=sample_count,
            ready=sample_count >= self.min_samples,
            reset_reason=reset_reason,
        )

    def current(self, trajectory_key: str) -> dict[str, list[float]]:
        state = self._states.get(trajectory_key)
        if state is None:
            raise KeyError(f"관리 중인 trajectory가 아닙니다: {trajectory_key}")
        return {
            feature: [row[feature] for row in state.rows]
            for feature in self.features
        }

    def remove(self, trajectory_key: str) -> None:
        self._states.pop(trajectory_key, None)

    def _new_state(self, case_name: str) -> _TrajectoryState:
        return _TrajectoryState(case_name, deque(maxlen=self.window_size))

    @staticmethod
    def _discontinuity_reason(
        state: _TrajectoryState,
        case_name: str,
        sequence: int,
        timestamp_hours: float,
    ) -> str | None:
        if state.case_name != case_name:
            return "case_changed"
        if state.last_sequence is None or state.last_timestamp_hours is None:
            return None
        if sequence <= state.last_sequence:
            return "sequence_not_increasing"
        if sequence != state.last_sequence + 1:
            return "sequence_gap"
        if timestamp_hours <= state.last_timestamp_hours:
            return "timestamp_not_increasing"
        return None

    @staticmethod
    def _required_string(message: Mapping[str, Any], field: str) -> str:
        value = message.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field}는 비어 있지 않은 문자열이어야 합니다.")
        return value

    @staticmethod
    def _required_integer(message: Mapping[str, Any], field: str) -> int:
        value = message.get(field)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{field}는 정수여야 합니다.")
        return value

    @staticmethod
    def _required_finite_number(message: Mapping[str, Any], field: str) -> float:
        try:
            value = float(message[field])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{field}는 숫자여야 합니다.") from error
        if not math.isfinite(value):
            raise ValueError(f"{field}는 유한한 숫자여야 합니다.")
        return value

    @staticmethod
    def _finite_value(value: Any, feature: str) -> float:
        try:
            converted = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{feature} 값은 숫자여야 합니다.") from error
        if not math.isfinite(converted):
            raise ValueError(f"{feature} 값은 유한한 숫자여야 합니다.")
        return converted
