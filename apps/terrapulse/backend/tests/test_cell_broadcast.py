import copy
import unittest
from datetime import datetime

from alerts.cell_broadcast import warning_to_alert_parameters
from alerts.service import CellBroadcastService


def make_warning(**overrides):
    warning = {
        "id": 123,
        "location_id": "NSK_04",
        "location_name": "Dikchu",
        "risk_level": "high",
        "risk_score": 82.5,
        "affected_infrastructure": ["NH-10 corridor", "Dikchu bridge"],
    }
    warning.update(overrides)
    return warning


def make_location(**overrides):
    location = {
        "location_id": "NSK_04",
        "district": "Mangan",
        "state": "Sikkim",
        "lat_min": 27.45,
        "lat_max": 27.49,
        "lon_min": 88.57,
        "lon_max": 88.62,
    }
    location.update(overrides)
    return location


class FailingGateway:
    def dispatch(self, payload):
        raise RuntimeError("Simulated gateway unavailable")


class CellBroadcastServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = CellBroadcastService()

    def test_high_warning_produces_valid_simulation_payload(self):
        result = self.service.simulate(make_warning(), make_location())

        self.assertTrue(result["simulation"])
        self.assertEqual("SIMULATED_DISPATCH", result["status"])
        self.assertEqual("Severe", result["payload"]["severity"])
        self.assertEqual("Expected", result["payload"]["urgency"])
        self.assertEqual("Likely", result["payload"]["certainty"])

    def test_critical_warning_produces_valid_simulation_payload(self):
        result = self.service.simulate(make_warning(risk_level="critical"), make_location())

        self.assertEqual("Extreme", result["payload"]["severity"])
        self.assertEqual("Immediate", result["payload"]["urgency"])
        self.assertEqual("SIMULATED_DISPATCH", result["status"])

    def test_warning_geometry_is_preferred_when_available(self):
        geometry = {"type": "Polygon", "coordinates": [[[88, 27], [89, 27], [89, 28], [88, 28], [88, 27]]]}
        result = self.service.simulate(make_warning(geometry=geometry), make_location())

        self.assertEqual("warning_geometry", result["target"]["source"])
        self.assertEqual(geometry, result["target"]["geometry"])

    def test_missing_geometry_uses_explicit_demo_fallback(self):
        result = self.service.simulate(make_warning(), None)

        self.assertEqual("demo", result["target"]["source"])
        self.assertIsNone(result["target"]["geometry"])

    def test_network_simulation_has_no_fake_tower_or_device_counts(self):
        result = self.service.simulate(make_warning(), make_location())

        self.assertEqual("SIMULATED", result["network_simulation"]["status"])
        self.assertEqual([], result["network_simulation"]["target_cells"])
        self.assertIsNone(result["network_simulation"]["estimated_devices"])

    def test_cap_metadata_is_internally_consistent(self):
        result = self.service.simulate(make_warning(), make_location())
        payload = result["payload"]

        self.assertEqual("CAP-compatible", payload["format"])
        self.assertEqual("Exercise", payload["status"])
        self.assertEqual("Alert", payload["msgType"])
        self.assertEqual("Public", payload["scope"])
        for info in payload["info"]:
            self.assertEqual(payload["severity"], info["severity"])
            self.assertEqual(payload["urgency"], info["urgency"])
            self.assertEqual(payload["certainty"], info["certainty"])
            self.assertEqual(payload["area"], info["area"])

    def test_expiry_is_after_dispatch_time(self):
        result = self.service.simulate(make_warning(), make_location())

        self.assertGreater(
            datetime.fromisoformat(result["expires_at"]),
            datetime.fromisoformat(result["dispatched_at"]),
        )

    def test_multilingual_messages_are_included(self):
        result = self.service.simulate(make_warning(), make_location())

        self.assertEqual(["en", "hi", "ne"], result["payload"]["languages"])
        self.assertEqual(3, len(result["payload"]["messages"]))
        self.assertEqual({"en", "hi", "ne"}, {message["language"] for message in result["payload"]["messages"]})

    def test_gateway_failure_is_exposed(self):
        service = CellBroadcastService(gateway=FailingGateway())

        with self.assertRaises(RuntimeError):
            service.simulate(make_warning(), make_location())

    def test_simulation_does_not_mutate_warning_or_location(self):
        warning = make_warning()
        location = make_location()
        warning_copy = copy.deepcopy(warning)
        location_copy = copy.deepcopy(location)

        self.service.simulate(warning, location)

        self.assertEqual(warning_copy, warning)
        self.assertEqual(location_copy, location)


class AlertParameterTests(unittest.TestCase):
    def test_warning_levels_map_to_centralized_cap_parameters(self):
        self.assertEqual(("Extreme", "Immediate", "Likely"), tuple(warning_to_alert_parameters({"risk_level": "critical"}).values()))
        self.assertEqual(("Severe", "Expected", "Likely"), tuple(warning_to_alert_parameters({"risk_level": "high"}).values()))
        self.assertEqual(("Moderate", "Future", "Possible"), tuple(warning_to_alert_parameters({"risk_level": "moderate"}).values()))


if __name__ == "__main__":
    unittest.main()
