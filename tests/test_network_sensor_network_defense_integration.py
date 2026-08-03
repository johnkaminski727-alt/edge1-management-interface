#!/usr/bin/env python3
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SERVER = ROOT / "server"
sys.path.insert(0, str(SERVER))
SPEC = importlib.util.spec_from_file_location("network_defense_sensor_exporter", SERVER / "network_defense_sensor_exporter.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class NetworkSensorNetworkDefenseTests(unittest.TestCase):
    def base_snapshot(self):
        return {
            "overall_state": "observed",
            "traffic_controls_changed": False,
            "summary": {
                "component_count": 2,
                "observed_component_count": 1,
                "verified_enforcement_count": 1,
            },
            "components": {
                "ids": {"observed": True, "enforcement_verified": False},
                "spamhaus": {"observed": True, "enforcement_verified": True},
            },
            "correlation_context": {"event_count": 3},
            "limitations": [],
        }

    def test_absent_sensor_context_preserves_snapshot(self):
        snapshot = self.base_snapshot()
        result = MODULE.augment_snapshot(snapshot, {"summary": {}})
        self.assertNotIn("network_sensor", result["components"])
        self.assertEqual(result["summary"]["component_count"], 2)

    def test_sensor_is_first_class_observed_component(self):
        snapshot = self.base_snapshot()
        result = MODULE.augment_snapshot(snapshot, {
            "network_sensor_context": {
                "profile": "owner-full",
                "mode": "passive_mirror",
                "restricted_payloads_copied": False,
            },
            "summary": {
                "network_sensor_event_count": 17,
                "category_counts": {"network": 12, "ids": 3, "dns": 2},
            },
        })
        sensor = result["components"]["network_sensor"]
        self.assertEqual(sensor["state"], "observed")
        self.assertEqual(sensor["metrics"]["normalized_events"], 17)
        self.assertEqual(sensor["metrics"]["network_events"], 12)
        self.assertFalse(sensor["enforcement_verified"])
        self.assertEqual(result["summary"]["component_count"], 3)
        self.assertEqual(result["summary"]["verified_enforcement_count"], 1)
        self.assertFalse(result["traffic_controls_changed"])

    def test_connected_empty_sensor_is_ready_not_observed(self):
        result = MODULE.augment_snapshot(self.base_snapshot(), {
            "network_sensor_context": {"profile": "owner-full", "mode": "passive_mirror"},
            "summary": {"network_sensor_event_count": 0, "category_counts": {}},
        })
        self.assertEqual(result["components"]["network_sensor"]["state"], "ready")
        self.assertFalse(result["components"]["network_sensor"]["observed"])


if __name__ == "__main__":
    unittest.main()
