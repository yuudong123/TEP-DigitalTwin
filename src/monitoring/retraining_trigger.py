from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class TriggerDecision:
    requested: bool
    reason: str
    cooldown_remaining_seconds: float = 0.0


class RetrainingTrigger:
    """Case별 재학습 요청 cooldown을 파일에 보존한다."""

    def __init__(
        self,
        state_path: Path,
        *,
        enabled: bool = True,
        cooldown_hours: float = 24.0,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if cooldown_hours <= 0:
            raise ValueError("cooldown_hours는 0보다 커야 합니다.")
        self.state_path = state_path
        self.enabled = enabled
        self.cooldown = timedelta(hours=cooldown_hours)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._requested_at = self._load_state()

    def evaluate(
        self,
        *,
        case_name: str,
        drift_status: str,
        quality_valid: bool,
    ) -> TriggerDecision:
        if drift_status != "CONFIRMED_DRIFT":
            return TriggerDecision(False, "confirmed_drift_required")
        if not quality_valid:
            return TriggerDecision(False, "data_quality_failed")
        if not self.enabled:
            return TriggerDecision(False, "retraining_disabled")

        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("clock은 시간대가 있는 datetime을 반환해야 합니다.")
        now = now.astimezone(timezone.utc)
        previous = self._requested_at.get(case_name)
        if previous is not None:
            remaining = self.cooldown - (now - previous)
            if remaining.total_seconds() > 0:
                return TriggerDecision(
                    False,
                    "cooldown_active",
                    remaining.total_seconds(),
                )

        self._requested_at[case_name] = now
        self._save_state()
        return TriggerDecision(True, "confirmed_drift")

    def _load_state(self) -> dict[str, datetime]:
        if not self.state_path.exists():
            return {}
        raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        if raw.get("schema_version") != "1.0":
            raise ValueError("지원하지 않는 재학습 trigger 상태 파일입니다.")

        result = {}
        for case_name, value in raw.get("requested_at", {}).items():
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                raise ValueError("재학습 요청 시각에는 시간대가 필요합니다.")
            result[case_name] = parsed.astimezone(timezone.utc)
        return result

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        payload = {
            "schema_version": "1.0",
            "requested_at": {
                case_name: requested_at.isoformat(timespec="seconds")
                for case_name, requested_at in sorted(self._requested_at.items())
            },
        }
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(self.state_path)
