"""Regression tests for the /rpc get_geo_data function.

This function was once shadowed by an /api/geo route handler that reused the
same Python name. The later definition rebound the module global, so the RPC
dispatch called the wrong function and the map's layer fetch failed with
"get_geo_data() got an unexpected keyword argument 'region_id'".

The RPC name and any route handler name must stay distinct.
"""

import unittest

from fastapi.testclient import TestClient

import main


class GeoDataRpcTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_rpc_function_accepts_region_id(self):
        data = main.get_geo_data(region_id="ner_india")

        self.assertIsInstance(data, dict)
        self.assertIn("infrastructure", data)
        self.assertIn("historical_landslides", data)

    def test_rpc_endpoint_returns_geometry_layers(self):
        response = self.client.post(
            "/rpc",
            json={"module": "main", "func": "get_geo_data",
                  "args": {"region_id": "ner_india"}})

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertIn("nh10_route", body)
        self.assertIn("historical_landslides", body)
        self.assertIn("infrastructure", body)

    def test_api_geo_route_still_serves_layers(self):
        response = self.client.get("/api/geo?region=ner_india")

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertIn("nh10_route", body)
        self.assertIn("infrastructure", body)


if __name__ == "__main__":
    unittest.main()