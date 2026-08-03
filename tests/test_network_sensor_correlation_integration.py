#!/usr/bin/env python3
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SERVER = ROOT / "server"
sys.path.insert(0, str(SERVER))
SPEC = importlib.util.spec_from_file_location("security_correlation_sensor_exporter", SERVER / "security_correlation_sensor_exporter.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class NetworkSensorCorrelationTests(unittest.TestCase):
    def sources(self, root: Path):
        security = root / "security.json"
        network = root / "network.json"
        operations = root / "operations.json"
        spamhaus = root / "spamhaus.txt"
        security.write_text(json.dumps({"recent_alerts": []}), encoding="utf-8")
        network.write_text("{}", encoding="utf-8")
        operations.write_text("{}", encoding="utf-8")
        spamhaus.write_text("combined4=1\ndrop6=0\n", encoding="utf-8")
        return security, network, operations, spamhaus

    def test_absent_sensor_preserves_existing_four_source_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = self.sources(root)
            snapshot = MODULE.build_snapshot(*sources, sensor_path=root / "missing.json")
            self.assertEqual(snapshot["summary"]["source_count"], 4)
            self.assertNotIn("network_sensor", snapshot["source_status"])
            self.assertNotIn("network_sensor_context", snapshot)

    def test_sensor_events_are_minimized_and_correlated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = self.sources(root)
            sensor_path = root / "sensor.json"
            sensor_path.write_text(json.dumps({
                "contract": "wwcx.edge1-network-sensor.v1",
                "visibility": "restricted-owner-full",
                "profile": "owner-full",
                "mode": "passive_mirror",
                "interface": "enp3s0",
                "recent_suricata_events": [
                    {
                        "timestamp": "2026-08-03T02:00:00Z",
                        "event_type": "alert",
                        "src_ip": "192.168.1.10",
                        "dest_ip": "203.0.113.7",
                        "payload": "restricted packet payload",
                        "alert": {"signature": "Synthetic sensor alert", "severity": 2, "category": "test"},
                    },
                    {
                        "timestamp": "2026-08-03T02:00:20Z",
                        "event_type": "dns",
                        "src_ip": "192.168.1.10",
                        "dest_ip": "203.0.113.7",
                        "dns": {"rrname": "example.test"},
                    },
                ],
                "recent_zeek_events": [
                    {
                        "zeek_log": "http",
                        "ts": 1785722440,
                        "id.orig_h": "192.168.1.10",
                        "id.resp_h": "203.0.113.7",
                        "host": "example.test",
                        "uri": "/owner-only",
                        "username": "not-copied",
                    }
                ],
            }), encoding="utf-8")

            snapshot = MODULE.build_snapshot(*sources, sensor_path=sensor_path, window_seconds=300)
            self.assertEqual(snapshot["summary"]["source_count"], 5)
            self.assertEqual(snapshot["summary"]["network_sensor_event_count"], 3)
            self.assertIn("network_sensor", snapshot["source_status"])
            self.assertGreaterEqual(snapshot["summary"]["category_counts"].get("ids", 0), 1)
            self.assertGreaterEqual(snapshot["summary"]["category_counts"].get("dns", 0), 1)
            self.assertGreaterEqual(snapshot["summary"]["category_counts"].get("network", 0), 1)
            sensor_events = [item for item in snapshot["events"] if item.get("sensor") == "edge1-passive"]
            self.assertEqual(len(sensor_events), 3)
            for event in sensor_events:
                for forbidden in ("payload", "alert", "dns", "http", "uri", "username"):
                    self.assertNotIn(forbidden, event)
            self.assertTrue(snapshot["correlations"])
            self.assertFalse(snapshot["network_sensor_context"]["restricted_payloads_copied"])

    def test_invalid_sensor_contract_is_visible_without_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = self.sources(root)
            sensor = root / "sensor.json"
            sensor.write_text(json.dumps({"contract": "unexpected", "visibility": "restricted-owner-full"}), encoding="utf-8")
            snapshot = MODULE.build_snapshot(*sources, sensor_path=sensor)
            self.assertIn("network sensor contract is unsupported", snapshot["warnings"])
            self.assertEqual(snapshot["summary"]["source_count"], 4)


if __name__ == "__main__":
    unittest.main()
