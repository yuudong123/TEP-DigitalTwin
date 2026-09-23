from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class DriftThresholds:
    psi_warning: float = 0.10
    psi_strong: float = 0.25
    ks_statistic: float = 0.15
    ks_q_value: float = 0.01
    caution_ratio: float = 0.10
    drift_ratio: float = 0.20
    min_samples: int = 20
    confirmation_count: int = 3


@dataclass(frozen=True)
class FeatureDrift:
    feature: str
    psi: float
    ks_statistic: float
    q_value: float
    drifted: bool


@dataclass(frozen=True)
class DriftResult:
    status: str
    drifted_feature_count: int
    monitored_feature_count: int
    drifted_feature_ratio: float
    consecutive_drift_count: int
    features: list[FeatureDrift]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def quantile_edges(reference: Sequence[float], bins: int = 10) -> np.ndarray:
    values = _finite_values(reference)
    if values.size == 0:
        raise ValueError("기준 데이터가 비어 있습니다.")
    if bins < 2:
        raise ValueError("bins는 2 이상이어야 합니다.")

    edges = np.unique(np.quantile(values, np.linspace(0.0, 1.0, bins + 1)))
    if edges.size < 2:
        center = float(edges[0])
        scale = max(abs(center) * 1e-6, 1e-6)
        edges = np.array([center - scale, center + scale])

    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def population_stability_index(
    reference: Sequence[float],
    current: Sequence[float],
    bins: int = 10,
    epsilon: float = 1e-6,
) -> float:
    reference_values = _finite_values(reference)
    current_values = _finite_values(current)
    if reference_values.size == 0 or current_values.size == 0:
        raise ValueError("PSI 계산에는 비어 있지 않은 데이터가 필요합니다.")

    edges = quantile_edges(reference_values, bins)
    reference_counts, _ = np.histogram(reference_values, bins=edges)
    current_counts, _ = np.histogram(current_values, bins=edges)

    reference_ratio = reference_counts / reference_values.size
    current_ratio = current_counts / current_values.size
    reference_ratio = np.clip(reference_ratio, epsilon, None)
    current_ratio = np.clip(current_ratio, epsilon, None)

    return float(
        np.sum((current_ratio - reference_ratio) * np.log(current_ratio / reference_ratio))
    )


def ks_test(reference: Sequence[float], current: Sequence[float]) -> tuple[float, float]:
    """Two-sample KS statistic과 점근적 p-value를 계산한다."""
    left = np.sort(_finite_values(reference))
    right = np.sort(_finite_values(current))
    if left.size == 0 or right.size == 0:
        raise ValueError("KS 계산에는 비어 있지 않은 데이터가 필요합니다.")

    combined = np.concatenate((left, right))
    left_cdf = np.searchsorted(left, combined, side="right") / left.size
    right_cdf = np.searchsorted(right, combined, side="right") / right.size
    statistic = float(np.max(np.abs(left_cdf - right_cdf)))

    effective_n = left.size * right.size / (left.size + right.size)
    root_n = math.sqrt(effective_n)
    scaled = (root_n + 0.12 + 0.11 / root_n) * statistic
    terms = [
        2.0 * ((-1.0) ** (index - 1)) * math.exp(-2.0 * index * index * scaled * scaled)
        for index in range(1, 101)
    ]
    p_value = min(1.0, max(0.0, sum(terms)))
    return statistic, p_value


def benjamini_hochberg(p_values: Sequence[float]) -> list[float]:
    if not p_values:
        return []
    values = np.asarray(p_values, dtype=float)
    if np.any(~np.isfinite(values)) or np.any((values < 0.0) | (values > 1.0)):
        raise ValueError("p-value는 0과 1 사이의 유한한 값이어야 합니다.")

    order = np.argsort(values)
    ranked = values[order]
    count = values.size
    adjusted = ranked * count / np.arange(1, count + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.clip(adjusted, 0.0, 1.0)

    result = np.empty(count)
    result[order] = adjusted
    return result.tolist()


class DriftDetector:
    def __init__(self, thresholds: DriftThresholds | None = None) -> None:
        self.thresholds = thresholds or DriftThresholds()
        self._consecutive_drift_count = 0

    def reset(self) -> None:
        """연속 Drift 상태를 현재 trajectory 단절에 맞춰 초기화한다."""
        self._consecutive_drift_count = 0

    def detect(
        self,
        reference: Mapping[str, Sequence[float]],
        current: Mapping[str, Sequence[float]],
    ) -> DriftResult:
        feature_names = sorted(reference)
        if not feature_names:
            raise ValueError("감시할 기준 Feature가 없습니다.")
        if set(feature_names) != set(current):
            raise ValueError("기준 데이터와 현재 창의 Feature가 일치하지 않습니다.")

        sample_counts = [_finite_values(current[name]).size for name in feature_names]
        if min(sample_counts) < self.thresholds.min_samples:
            self._consecutive_drift_count = 0
            return DriftResult(
                status="INSUFFICIENT_DATA",
                drifted_feature_count=0,
                monitored_feature_count=len(feature_names),
                drifted_feature_ratio=0.0,
                consecutive_drift_count=0,
                features=[],
            )

        raw_results: list[tuple[str, float, float, float]] = []
        for name in feature_names:
            psi = population_stability_index(reference[name], current[name])
            statistic, p_value = ks_test(reference[name], current[name])
            raw_results.append((name, psi, statistic, p_value))

        q_values = benjamini_hochberg([item[3] for item in raw_results])
        features: list[FeatureDrift] = []
        for (name, psi, statistic, _), q_value in zip(raw_results, q_values, strict=True):
            drifted = psi >= self.thresholds.psi_strong or (
                psi >= self.thresholds.psi_warning
                and statistic >= self.thresholds.ks_statistic
                and q_value < self.thresholds.ks_q_value
            )
            features.append(FeatureDrift(name, psi, statistic, q_value, drifted))

        drifted_count = sum(item.drifted for item in features)
        ratio = drifted_count / len(features)
        if ratio >= self.thresholds.drift_ratio:
            self._consecutive_drift_count += 1
            status = (
                "CONFIRMED_DRIFT"
                if self._consecutive_drift_count >= self.thresholds.confirmation_count
                else "DRIFT"
            )
        else:
            self._consecutive_drift_count = 0
            status = "CAUTION" if ratio >= self.thresholds.caution_ratio else "NORMAL"

        return DriftResult(
            status=status,
            drifted_feature_count=drifted_count,
            monitored_feature_count=len(features),
            drifted_feature_ratio=ratio,
            consecutive_drift_count=self._consecutive_drift_count,
            features=features,
        )


def _finite_values(values: Sequence[float]) -> np.ndarray:
    converted = np.asarray(values, dtype=float)
    return converted[np.isfinite(converted)]
