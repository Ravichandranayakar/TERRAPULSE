import unittest

from fastapi.testclient import TestClient

import main


class RiskApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_predict_batch_returns_standard_contract(self):
        response = self.client.post(
            "/api/risk/predict-batch",
            json={
                "cells": [
                    {
                        "cell_id": "test-cell",
                        "rainfall_24h": 120,
                        "soil_moisture": 0.8,
                        "slope": 35,
                    }
                ]
            },
        )

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("development", body["predictor"])
        self.assertEqual("rule_based", body["predictor_type"])
        self.assertEqual("test-cell", body["predictions"][0]["cell_id"])
        self.assertIn("risk_score", body["predictions"][0])
        self.assertIn("contributing_factors", body["predictions"][0])

    def test_predict_batch_rejects_empty_payload(self):
        response = self.client.post("/api/risk/predict-batch", json={"cells": []})

        self.assertEqual(422, response.status_code)


if __name__ == "__main__":
    unittest.main()
