#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / "server" / "security_operations_exporter.py"
SPEC = importlib.util.spec_from_file_location("security_operations_exporter", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SecurityOperationsNormalizationTests(unittest.TestCase):
    def test_nested_eve_alert_is_flattened_and_classified(self):
        raw = {
            "timestamp": "2026-07-29T07:57:57+00:00",
            "flow_id": 123456789012345,
            "src_ip": "10.77.0.10",
            "src_port": 52430,
            "dest_ip": "132.226.247.73",
            "dest_port": 443,
            "proto": "TCP",
            "app_proto": "tls",
            "alert": {
                "action": "allowed",
                "gid": 1,
                "signature_id": 2034647,
                "rev": 2,
                "signature": "ET INFO Device Retrieving External IP Address Detected",
                "category": "Device Retrieving External IP Address Detected",
                "severity": 3,
            },
            "explanation": {
                "title": "Unclassified Suricata alert",
                "risk": "unknown",
                "meaning": "Suricata detected a rule match.",
                "recommendation": "Review source and rule details.",
            },
            "payload": "must-not-be-exported",
            "packet": "must-not-be-exported",
        }

        alert = MODULE.sanitize_alert(raw)
        self.assertIsNotNone(alert)
        assert alert is not None
        self.assertEqual(alert["signature"], "ET INFO Device Retrieving External IP Address Detected")
        self.assertEqual(alert["explanation"]["title"], alert["signature"])
        self.assertEqual(alert["risk"], "low")
        self.assertEqual(alert["suricata_severity"], 3)
        self.assertEqual(alert["source_port"], 52430)
        self.assertEqual(alert["destination_port"], 443)
        self.assertEqual(alert["protocol"], "TCP")
        self.assertEqual(alert["app_protocol"], "tls")
        self.assertEqual(alert["signature_id"], 2034647)
        self.assertEqual(alert["gid"], 1)
        self.assertEqual(alert["rev"], 2)
        self.assertEqual(alert["flow_id"], 123456789012345)
        self.assertEqual(alert["category"], "Device Retrieving External IP Address Detected")
        self.assertEqual(alert["action"], "allowed")
        self.assertIn(alert["signature"], alert["explanation"]["meaning"])
        self.assertNotIn("payload", alert)
        self.assertNotIn("packet", alert)
        self.assertNotIn("alert", alert)
        self.assertTrue(alert["normalization"]["sanitized"])
        self.assertFalse(alert["normalization"]["packet_payload_included"])
        self.assertFalse(alert["normalization"]["raw_event_included"])

    def test_source_collector_semantic_fields_are_preserved(self):
        raw = {
            "timestamp": "2026-07-29T08:25:00+00:00",
            "signature": "Collector contract test",
            "severity": 2,
            "source": "10.77.0.10",
            "source_port": 53001,
            "destination": "192.0.2.10",
            "destination_port": 443,
            "protocol": "TCP",
            "application_protocol": "tls",
            "category": "Test category",
            "action": "allowed",
            "signature_id": 2030001,
            "generator_id": 1,
            "revision": 4,
            "flow_id": 987654321,
        }
        alert = MODULE.sanitize_alert(raw)
        self.assertIsNotNone(alert)
        assert alert is not None
        self.assertEqual(alert["gid"], 1)
        self.assertEqual(alert["rev"], 4)
        self.assertEqual(alert["signature_id"], 2030001)
        self.assertEqual(alert["app_protocol"], "tls")
        self.assertEqual(alert["flow_id"], 987654321)
        self.assertEqual(alert["risk"], "medium")

    def test_explicit_risk_overrides_numeric_suricata_severity(self):
        alert = MODULE.sanitize_alert({
            "risk": "critical",
            "alert": {"severity": 3, "signature": "Local policy test"},
        })
        self.assertEqual(alert["risk"], "critical")

    def test_invalid_ports_and_identifiers_are_not_published(self):
        alert = MODULE.sanitize_alert({
            "src_port": 0,
            "dest_port": 70000,
            "alert": {
                "signature": "Malformed metadata test",
                "signature_id": -1,
                "gid": -4,
                "rev": -2,
            },
        })
        self.assertIsNone(alert["source_port"])
        self.assertIsNone(alert["destination_port"])
        self.assertIsNone(alert["signature_id"])
        self.assertIsNone(alert["gid"])
        self.assertIsNone(alert["rev"])

    def test_alert_list_remains_bounded(self):
        raw = [{"alert": {"signature": f"alert-{index}"}} for index in range(75)]
        alerts = MODULE.sanitize_alerts(raw)
        self.assertEqual(len(alerts), MODULE.MAX_ALERTS)
        self.assertEqual(alerts[0]["signature"], "alert-0")
        self.assertEqual(alerts[-1]["signature"], "alert-49")


if __name__ == "__main__":
    unittest.main()
