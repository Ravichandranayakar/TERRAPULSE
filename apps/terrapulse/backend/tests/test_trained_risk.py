"""Contract tests for the trained susceptibility predictor.

The artifact is the active version resolved through models/registry.json, produced
by scripts/train_landslide_model.py. These tests skip when it is absent, so the
backend suite still runs in a container that does not ship the model.

Feature values here are synthetic. They exercise the response contract only;
they assert nothing about accuracy. Performance numbers live in
model_evaluation.md and the active version's metrics.json.
"""

import unittest

from fastapi.testclient import TestClient

import main
from risk.schemas import TrainedRiskFeatureInput
from risk.trained_predictor import (ArtifactUnavailable, TrainedMLRiskPredictor,
                                    load_artifact)

try:
    _ARTIFACT = load_artifact()
except ArtifactUnavailable:
    _ARTIFACT = None


def synthetic_payload(model_features, categorical):
    features = {name: 0.0 for name in model_features}
    for name in categorical:
        features[name] = ""
    return {"cell_id": "test-cell", "lat": 25.5, "lon": 92.0, "features": features}


@unittest.skipIf(_ARTIFACT is None, "trained artifact not present")
class TrainedPredictorTests(unittest.TestCase):
    def setUp(self):
        self.predictor = TrainedMLRiskPredictor(_ARTIFACT)
        self.categorical = list(_ARTIFACT.schema.get("categorical_features", []))
        self.payload = synthetic_payload(self.predictor.features, self.categorical)

    def test_scores_and_returns_the_shared_contract(self):
        prediction = self.predictor.predict(TrainedRiskFeatureInput(**self.payload))

        self.assertGreaterEqual(prediction.risk_score, 0.0)
        self.assertLessEqual(prediction.risk_score, 100.0)
        self.assertIn(prediction.risk_class, {"LOW", "MODERATE", "HIGH", "CRITICAL"})
        self.assertEqual(self.predictor.name, prediction.predictor)
        self.assertEqual("trained_susceptibility_classifier", prediction.predictor_type)
        self.assertIsInstance(prediction.warning_ready, bool)

    def test_incomplete_payload_is_rejected_not_padded(self):
        payload = synthetic_payload(self.predictor.features, self.categorical)
        payload["features"].pop(self.predictor.features[0])

        with self.assertRaises(ValueError):
            self.predictor.predict(TrainedRiskFeatureInput(**payload))

    def test_identical_inputs_are_deterministic(self):
        first = self.predictor.predict(TrainedRiskFeatureInput(**self.payload))
        second = self.predictor.predict(TrainedRiskFeatureInput(**self.payload))

        self.assertEqual(first.model_dump(), second.model_dump())


class TrainedRiskApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_model_status_reports_availability(self):
        body = self.client.get("/api/risk/model-status").json()

        self.assertIn("available", body)
        self.assertIn("artifact_dir", body)

    @unittest.skipIf(_ARTIFACT is None, "trained artifact not present")
    def test_predict_trained_returns_contract(self):
        predictor = TrainedMLRiskPredictor(_ARTIFACT)
        categorical = list(_ARTIFACT.schema.get("categorical_features", []))
        response = self.client.post(
            "/api/risk/predict-trained",
            json=synthetic_payload(predictor.features, categorical))

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(predictor.name, body["predictor"])
        self.assertEqual("trained_susceptibility_classifier", body["predictor_type"])
        self.assertEqual("test-cell", body["cell_id"])
        self.assertIn("risk_score", body)
        self.assertIn("contributing_factors", body)

    @unittest.skipIf(_ARTIFACT is None, "trained artifact not present")
    def test_predict_trained_rejects_incomplete_payload(self):
        predictor = TrainedMLRiskPredictor(_ARTIFACT)
        payload = synthetic_payload(predictor.features, [])
        payload["features"] = {}

        response = self.client.post("/api/risk/predict-trained", json=payload)

        self.assertEqual(422, response.status_code)
        self.assertIn("missing", response.json()["detail"])

    def test_development_endpoint_is_unchanged(self):
        response = self.client.post(
            "/api/risk/predict",
            json={"cell_id": "test-cell", "rainfall_24h": 120, "slope": 35})

        self.assertEqual(200, response.status_code)
        self.assertEqual("development", response.json()["predictor"])
        self.assertEqual("rule_based", response.json()["predictor_type"])


if __name__ == "__main__":
    unittest.main()