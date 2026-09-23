import importlib.util
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.inference.model_loader import determine_status
from src.inference.prediction_schema import RISK_TARGETS, validate_prediction
from src.inference.main import decode_sensor_message
from src.inference.temporal_features import (
    TrajectoryFeatureBuffer,
    base_features_from_feature_list,
    build_latest_features,
)
from kafka.message_schema import build_sensor_message


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = PROJECT_ROOT / "models" / "production" / "v1.0.0"


def load_feature_list() -> list[str]:
    payload = json.loads((MODEL_DIR / "feature_list.json").read_text(encoding="utf-8"))
    return payload["features"]


def load_offline_module():
    path = PROJECT_ROOT / "src" / "data" / "05-build_temporal_features.py"
    spec = importlib.util.spec_from_file_location("offline_temporal_test", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeKafkaMessage:
    def __init__(self, key: bytes | None, value: bytes | None):
        self._key = key
        self._value = value

    def key(self):
        return self._key

    def value(self):
        return self._value


class InferenceRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ordered_features = load_feature_list()
        cls.base_features = base_features_from_feature_list(cls.ordered_features)
        # Deterministic non-linear inputs keep unit tests independent of raw CSVs.
        schema = pd.read_csv(PROJECT_ROOT / "data" / "metadata" / "feature_schema.csv")
        step = np.arange(21, dtype=float)
        cls.trajectory = pd.DataFrame({
            name: np.sin(step / (index + 1)) + step ** 2 * 0.01 + index
            for index, name in enumerate(schema["column"])
            if name not in ("Id", "Time")
        })
        cls.trajectory["Id"] = 1
        cls.trajectory["Time"] = step * 0.05

    def test_online_features_match_training_features(self):
        trajectory = self.trajectory.iloc[:21].copy()
        trajectory["case"] = "case1"
        trajectory["trajectory_key"] = "case1::1"
        for column in [
            "rul_hours", "rul_fraction", "failure_within_4h",
            "failure_within_2h", "failure_within_1h",
        ]:
            trajectory[column] = 0

        offline = load_offline_module().build_features(trajectory, self.base_features)
        expected = offline.iloc[-1][self.ordered_features].to_numpy(dtype=np.float32)
        rows = trajectory[self.base_features].to_dict("records")
        actual = build_latest_features(
            rows, self.base_features, self.ordered_features
        ).iloc[0].to_numpy(dtype=np.float32)
        np.testing.assert_array_equal(actual, expected)

    def test_buffer_waits_for_twenty_history_rows(self):
        buffer = TrajectoryFeatureBuffer(self.ordered_features)
        results = []
        for sequence, (_, row) in enumerate(self.trajectory.iloc[:21].iterrows()):
            results.append(buffer.add({
                "trajectory_key": "case1::1",
                "sequence": sequence,
                "timestamp_hours": float(row["Time"]),
                "values": {name: float(row[name]) for name in self.base_features},
            }))
        self.assertTrue(all(not item.ready for item in results[:20]))
        self.assertTrue(results[20].ready)
        self.assertEqual(list(results[20].features.columns), self.ordered_features)

    def test_sensor_decoder_rejects_mismatched_kafka_key(self):
        row = self.trajectory.iloc[0].to_dict()
        sensor = build_sensor_message(
            "case1", row, 0, replayed_at=datetime.now(timezone.utc)
        )
        message = FakeKafkaMessage(
            b"case1::999", json.dumps(sensor).encode("utf-8")
        )
        with self.assertRaisesRegex(ValueError, "Kafka key"):
            decode_sensor_message(message)

    def test_status_uses_most_urgent_threshold_first(self):
        thresholds = {target: 0.5 for target in RISK_TARGETS}
        scores = {
            "failure_within_4h": 0.9,
            "failure_within_2h": 0.8,
            "failure_within_1h": 0.7,
        }
        self.assertEqual(determine_status(scores, thresholds), (
            "CRITICAL", "failure_within_1h"
        ))

    def test_prediction_rejects_probability_over_one(self):
        risk = {
            target: {"score": 0.2, "threshold": 0.5, "alert": False}
            for target in RISK_TARGETS
        }
        risk["failure_within_1h"]["score"] = 1.1
        prediction = {
            "schema_version": "1.0",
            "model_version": "v1.0.0",
            "trajectory_key": "case1::1",
            "timestamp_hours": 1.0,
            "rul": {"hours": 2.0},
            "risk": risk,
            "status": "NORMAL",
            "explanation_model": "failure_within_4h",
            "top_risk_factors": [],
        }
        with self.assertRaisesRegex(ValueError, "0과 1"):
            validate_prediction(prediction)


if __name__ == "__main__":
    unittest.main()
