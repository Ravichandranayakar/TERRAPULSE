import unittest

from risk.predictor import DevelopmentRiskPredictor
from risk.schemas import RiskFeatureInput


def make_features(**overrides: float) -> RiskFeatureInput:
    values = {
        "cell_id": "test-cell",
        "rainfall_1h": 5.0,
        "rainfall_3h": 15.0,
        "rainfall_6h": 30.0,
        "rainfall_24h": 60.0,
        "antecedent_rainfall": 90.0,
        "soil_moisture": 0.4,
        "elevation": 1500.0,
        "slope": 30.0,
        "aspect": 180.0,
        "historical_susceptibility": 0.5,
    }
    values.update(overrides)
    return RiskFeatureInput(**values)


class DevelopmentRiskPredictorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.predictor = DevelopmentRiskPredictor()

    def test_identical_inputs_are_deterministic(self) -> None:
        features = make_features()

        first = self.predictor.predict(features)
        second = self.predictor.predict(features)

        self.assertEqual(first.model_dump(), second.model_dump())

    def test_material_rainfall_change_changes_score_and_drivers(self) -> None:
        baseline = self.predictor.predict(make_features(antecedent_rainfall=20.0))
        saturated = self.predictor.predict(make_features(antecedent_rainfall=420.0))

        self.assertGreater(saturated.risk_score, baseline.risk_score)
        self.assertIn("Elevated antecedent rainfall contribution", saturated.drivers)

    def test_risk_class_thresholds_are_consistent(self) -> None:
        for score, expected in ((10.0, "LOW"), (40.0, "MODERATE"), (60.0, "HIGH"), (80.0, "CRITICAL")):
            self.assertEqual(expected, self.predictor._risk_class(score))

    def test_missing_features_are_reported_and_neutral_defaults_are_explicit(self) -> None:
        result = self.predictor.predict(RiskFeatureInput(cell_id="missing-cell"))

        self.assertIn("rainfall_24h", result.missing_features)
        self.assertEqual(0.0, result.features["rainfall_24h"])
        self.assertEqual("development", result.predictor)
        self.assertEqual("rule_based", result.predictor_type)

    def test_invalid_feature_ranges_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RiskFeatureInput(cell_id="invalid", soil_moisture=1.5)


if __name__ == "__main__":
    unittest.main()
