import unittest

import numpy as np

from src.monitoring.drift_detector import (
    DriftDetector,
    DriftThresholds,
    benjamini_hochberg,
    population_stability_index,
)


class DriftDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reference = {
            "feature_a": np.linspace(0.0, 1.0, 200),
            "feature_b": np.linspace(10.0, 20.0, 200),
        }

    def test_same_distribution_is_normal(self) -> None:
        detector = DriftDetector()
        result = detector.detect(self.reference, self.reference)
        self.assertEqual(result.status, "NORMAL")
        self.assertEqual(result.drifted_feature_count, 0)

    def test_shift_is_confirmed_after_three_checks(self) -> None:
        detector = DriftDetector(DriftThresholds(drift_ratio=0.20))
        shifted = {name: values + 100.0 for name, values in self.reference.items()}
        self.assertEqual(detector.detect(self.reference, shifted).status, "DRIFT")
        self.assertEqual(detector.detect(self.reference, shifted).status, "DRIFT")
        self.assertEqual(detector.detect(self.reference, shifted).status, "CONFIRMED_DRIFT")

    def test_small_window_is_not_evaluated(self) -> None:
        detector = DriftDetector()
        current = {name: values[:10] for name, values in self.reference.items()}
        result = detector.detect(self.reference, current)
        self.assertEqual(result.status, "INSUFFICIENT_DATA")

    def test_psi_is_zero_for_identical_values(self) -> None:
        self.assertAlmostEqual(
            population_stability_index(self.reference["feature_a"], self.reference["feature_a"]),
            0.0,
        )

    def test_benjamini_hochberg_preserves_input_order(self) -> None:
        adjusted = benjamini_hochberg([0.04, 0.001, 0.02])
        self.assertEqual(len(adjusted), 3)
        self.assertLess(adjusted[1], adjusted[2])
        self.assertLessEqual(adjusted[2], adjusted[0])


if __name__ == "__main__":
    unittest.main()
