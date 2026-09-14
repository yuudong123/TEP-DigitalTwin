from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import uuid4

from src.monitoring.drift_detector import DriftResult


SCHEMA_VERSION = "1.0"
EVENT_TYPE = "tep_drift_event"
ALLOWED_STATUSES = {
    "NORMAL",
    "CAUTION",
    "DRIFT",
    "CONFIRMED_DRIFT",
    "INSUFFICIENT_DATA",
}


def build_drift_event(
    *,
    trajectory_key: str,
    case_name: str,
    sequence: int,
    timestamp_hours: float,
    reference_version: str,
    model_version: str,
    window_start: float,
    window_end: float,
    window_samples: int,
    result: DriftResult,
    prediction_context: Mapping[str, Any] | None = None,
    retraining_requested: bool = False,
    reason: str = "",
    detected_at: datetime | None = None,
) -> dict[str, Any]:
    actual_detected_at = detected_at or datetime.now().astimezone()
    if actual_detected_at.tzinfo is None:
        raise ValueError("detected_at에는 시간대가 필요합니다.")

    event: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_type": EVENT_TYPE,
        "event_id": str(uuid4()),
        "detected_at": actual_detected_at.isoformat(timespec="seconds"),
        "trajectory_key": trajectory_key,
        "case": case_name,
        "sequence": sequence,
        "timestamp_hours": float(timestamp_hours),
        "reference_version": reference_version,
        "model_version": model_version,
        "window": {
            "samples": window_samples,
            "start_timestamp_hours": float(window_start),
            "end_timestamp_hours": float(window_end),
        },
        "status": result.status,
        "drifted_feature_count": result.drifted_feature_count,
        "monitored_feature_count": result.monitored_feature_count,
        "drifted_feature_ratio": result.drifted_feature_ratio,
        "features": [feature.__dict__ for feature in result.features],
        "prediction_context": dict(prediction_context) if prediction_context else None,
        "retraining_requested": retraining_requested,
        "reason": reason,
    }
    validate_drift_event(event)
    return event


def validate_drift_event(event: Mapping[str, Any]) -> None:
    required = {
        "schema_version", "event_type", "event_id", "detected_at",
        "trajectory_key", "case", "sequence", "timestamp_hours",
        "reference_version", "model_version", "window", "status",
        "drifted_feature_count", "monitored_feature_count",
        "drifted_feature_ratio", "features", "prediction_context",
        "retraining_requested", "reason",
    }
    missing = required - set(event)
    if missing:
        raise ValueError(f"Drift event 필수 필드가 없습니다: {sorted(missing)}")
    if event["schema_version"] != SCHEMA_VERSION or event["event_type"] != EVENT_TYPE:
        raise ValueError("지원하지 않는 Drift event schema입니다.")
    if event["status"] not in ALLOWED_STATUSES:
        raise ValueError("지원하지 않는 Drift 상태입니다.")
    if not isinstance(event["sequence"], int) or isinstance(event["sequence"], bool):
        raise ValueError("sequence는 정수여야 합니다.")
    if not 0.0 <= float(event["drifted_feature_ratio"]) <= 1.0:
        raise ValueError("drifted_feature_ratio는 0과 1 사이여야 합니다.")
    parsed = datetime.fromisoformat(str(event["detected_at"]))
    if parsed.tzinfo is None:
        raise ValueError("detected_at에는 시간대가 필요합니다.")
