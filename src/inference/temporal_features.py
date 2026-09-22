"""학습 당시와 동일한 728개 Temporal Feature를 실시간으로 생성한다.

입력: Kafka에서 받은 한 trajectory의 센서 메시지
처리: 최근 21개 시점(현재 포함 60분)을 메모리에 모아 변화량·평균 등을 계산
출력: Production 모델에 바로 넣을 수 있는 728개 Feature 한 행

중요: Producer의 실제 전송 속도가 아니라 메시지의 3분 간격 시간축을 사용한다.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


# 3분 간격 데이터에서 현재 시점까지 60분을 포함하려면 총 21행이 필요하다.
# 예: 0분, 3분, ..., 60분
WINDOW_ROWS = 21
EXPECTED_INTERVAL_HOURS = 0.05
EXPECTED_FEATURE_COUNT = 728


def base_features_from_feature_list(features: list[str]) -> list[str]:
    """Feature 목록에서 변환 접미사가 없는 52개 기본 변수를 찾는다."""
    base_features = [feature for feature in features if "__" not in feature]
    if len(base_features) != 52:
        raise ValueError(f"기본 Feature는 52개여야 합니다: {len(base_features)}")
    return base_features


def _slope_60m(values: np.ndarray) -> np.ndarray:
    """학습 코드의 21개 시점 선형회귀 기울기와 동일하게 계산한다."""
    x = np.arange(WINDOW_ROWS, dtype=np.float32) * EXPECTED_INTERVAL_HOURS
    x_centered = x - x.mean()
    denominator = float(np.sum(x_centered**2))
    return np.tensordot(values, x_centered, axes=([0], [0])) / denominator


def build_latest_features(
    rows: list[dict[str, Any]],
    base_features: list[str],
    ordered_features: list[str],
) -> pd.DataFrame:
    """최근 21개 센서 행에서 현재 시점의 728개 Feature 한 행을 만든다."""
    if len(rows) < WINDOW_ROWS:
        raise ValueError(f"추론에는 최소 {WINDOW_ROWS}개 메시지가 필요합니다.")

    # 버퍼에 더 많은 행이 전달돼도 현재 시점 기준 최근 21행만 사용한다.
    recent = rows[-WINDOW_ROWS:]
    # Match the training pipeline's vectorized operation order exactly.
    base = pd.DataFrame(recent, columns=base_features).astype(np.float32)
    past_5m = (2.0 / 3.0) * base.shift(2) + (1.0 / 3.0) * base.shift(1)
    delta_5m = base - past_5m
    delta_15m = base - base.shift(5)
    delta_60m = base - base.shift(20)

    frames: list[pd.DataFrame] = [base.copy()]

    def renamed(frame: pd.DataFrame, suffix: str) -> pd.DataFrame:
        result = frame.copy()
        result.columns = [f"{column}{suffix}" for column in base_features]
        return result

    frames.extend([
        renamed(delta_5m, "__delta_5m"),
        renamed(delta_5m / (5.0 / 60.0), "__rate_5m_per_h"),
        renamed(base.rolling(6, min_periods=6).mean(), "__mean_15m"),
        renamed(base.rolling(6, min_periods=6).std(ddof=0), "__std_15m"),
        renamed(delta_15m, "__delta_15m"),
        renamed(delta_15m / 0.25, "__rate_15m_per_h"),
        renamed(base.rolling(11, min_periods=11).mean(), "__mean_30m"),
        renamed(base.rolling(11, min_periods=11).std(ddof=0), "__std_30m"),
        renamed(base.rolling(11, min_periods=11).max(), "__max_30m"),
        renamed(base.rolling(11, min_periods=11).min(), "__min_30m"),
        renamed(delta_60m, "__delta_60m"),
        renamed(delta_60m.copy(), "__rate_60m_per_h"),
    ])

    values = base.to_numpy(dtype=np.float32)
    slopes = np.full(values.shape, np.nan, dtype=np.float32)
    windows = np.lib.stride_tricks.sliding_window_view(
        values, window_shape=WINDOW_ROWS, axis=0
    )
    x = np.arange(WINDOW_ROWS, dtype=np.float32) * EXPECTED_INTERVAL_HOURS
    x_centered = x - x.mean()
    denominator = float(np.sum(x_centered**2))
    slopes[WINDOW_ROWS - 1:] = (
        np.tensordot(windows, x_centered, axes=([2], [0])) / denominator
    ).astype(np.float32)
    frames.append(renamed(pd.DataFrame(slopes, columns=base_features), "__slope_60m_per_h"))
    generated_frame = pd.concat(frames, axis=1).iloc[[-1]]

    # 모델은 학습 당시의 열 순서가 달라지면 잘못 예측할 수 있으므로
    # feature_list.json의 728개 순서로 다시 배열한다.
    missing = [feature for feature in ordered_features if feature not in generated_frame.columns]
    if missing:
        raise ValueError(f"생성되지 않은 Feature가 있습니다: {missing[:5]}")
    if len(ordered_features) != EXPECTED_FEATURE_COUNT:
        raise ValueError(f"모델 Feature는 728개여야 합니다: {len(ordered_features)}")

    frame = generated_frame[ordered_features].reset_index(drop=True).astype(np.float32)
    if not np.isfinite(frame.to_numpy()).all():
        raise ValueError("Temporal Feature에 NaN 또는 무한대가 있습니다.")
    return frame


@dataclass(frozen=True)
class BufferResult:
    trajectory_key: str
    timestamp_hours: float
    sequence: int
    buffered_rows: int
    ready: bool
    features: pd.DataFrame | None


class TrajectoryFeatureBuffer:
    """trajectory별 최근 60분(21행)을 메모리에 보관한다."""

    def __init__(self, ordered_features: list[str]) -> None:
        self.ordered_features = ordered_features
        self.base_features = base_features_from_feature_list(ordered_features)
        self._rows: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=WINDOW_ROWS)
        )
        self._last_sequence: dict[str, int] = {}
        self._last_time: dict[str, float] = {}

    def add(self, message: dict[str, Any]) -> BufferResult:
        """센서 메시지 한 개를 추가하고, 21개가 모이면 Feature를 반환한다."""
        key = str(message["trajectory_key"])
        sequence = int(message["sequence"])
        timestamp = float(message["timestamp_hours"])
        values = message.get("values")
        if not isinstance(values, dict):
            raise ValueError("Sensor 메시지의 values는 객체여야 합니다.")

        missing = [feature for feature in self.base_features if feature not in values]
        if missing:
            raise ValueError(f"Sensor 메시지에 기본 Feature가 없습니다: {missing[:5]}")

        # 메시지 누락이나 순서 뒤바뀜이 있으면 잘못된 시간 Feature가 만들어지므로
        # sequence와 timestamp가 직전 메시지에 이어지는지 확인한다.
        if key in self._last_sequence:
            expected_sequence = self._last_sequence[key] + 1
            expected_time = self._last_time[key] + EXPECTED_INTERVAL_HOURS
            if sequence != expected_sequence or not np.isclose(timestamp, expected_time, atol=1e-6):
                # 서로 다른 재생 실행이 같은 trajectory key로 다시 시작될 수 있다.
                if sequence == 0:
                    self.reset(key)
                else:
                    raise ValueError(
                        f"연속되지 않은 메시지: {key}, sequence={sequence}, "
                        f"expected={expected_sequence}, time={timestamp}"
                    )

        row = {feature: float(values[feature]) for feature in self.base_features}
        self._rows[key].append(row)
        self._last_sequence[key] = sequence
        self._last_time[key] = timestamp
        # 1~20번째 메시지는 준비 구간이고, 21번째부터 추론할 수 있다.
        ready = len(self._rows[key]) == WINDOW_ROWS
        feature_frame = None
        if ready:
            feature_frame = build_latest_features(
                list(self._rows[key]), self.base_features, self.ordered_features
            )

        return BufferResult(
            trajectory_key=key,
            timestamp_hours=timestamp,
            sequence=sequence,
            buffered_rows=len(self._rows[key]),
            ready=ready,
            features=feature_frame,
        )

    def reset(self, trajectory_key: str) -> None:
        """같은 trajectory가 sequence 0부터 다시 시작될 때 이전 버퍼를 비운다."""
        self._rows.pop(trajectory_key, None)
        self._last_sequence.pop(trajectory_key, None)
        self._last_time.pop(trajectory_key, None)
