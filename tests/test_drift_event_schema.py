import unittest
from datetime import datetime, timezone

from src.monitoring.drift_detector import DriftResult
from src.monitoring.event_schema import build_drift_event, validate_drift_event


class DriftEventSchemaTests(unittest.TestCase):
    def test_builds_valid_event_without_prediction(self) -> None:
        result = DriftResult("NORMAL", 0, 52, 0.0, 0, [])
        event = build_drift_event(
            trajectory_key="case1::1",
            case_name="case1",
            sequence=119,
            timestamp_hours=36.0,
            reference_version="v1.0.0",
            model_version="v1.0.0",
            window_start=30.05,
            window_end=36.0,
            window_samples=120,
            result=result,
            detected_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
        )
        validate_drift_event(event)
        self.assertIsNone(event["prediction_context"])
        self.assertEqual(event["status"], "NORMAL")

    def test_rejects_unknown_status(self) -> None:
        result = DriftResult("UNKNOWN", 0, 52, 0.0, 0, [])
        with self.assertRaises(ValueError):
            build_drift_event(
                trajectory_key="case1::1",
                case_name="case1",
                sequence=1,
                timestamp_hours=1.0,
                reference_version="v1.0.0",
                model_version="v1.0.0",
                window_start=0.0,
                window_end=1.0,
                window_samples=20,
                result=result,
                detected_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()
