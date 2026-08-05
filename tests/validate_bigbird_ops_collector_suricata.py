#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import tempfile
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / "server" / "bigbird_ops_collect.py"
SPEC = importlib.util.spec_from_file_location("bigbird_ops_collect", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class BigBirdSuricataCollectorTests(unittest.TestCase):
    def representative_event(self):
        return {
            "timestamp": "2026-07-29T08:25:00.000000+0000",
            "event_type": "alert",
            "src_ip": "10.77.0.10",
            "src_port": 53001,
            "dest_ip": "192.0.2.10",
            "dest_port": 443,
            "proto": "TCP",
            "app_proto": "tls",
            "flow_id": 123456789,
            "payload": "must-not-leave-eve",
            "packet": "must-not-leave-eve",
            "alert": {
                "action": "allowed",
                "gid": 1,
                "signature_id": 2030001,
                "rev": 4,
                "signature": "Device Retrieving External IP Address Detected",
                "category": "Potential Corporate Privacy Violation",
                "severity": 4,
                "metadata": {"raw": "must-not-leave-eve"},
            },
        }

    def test_managed_sensor_is_default_source(self):
        self.assertEqual(MODULE.SURICATA_SERVICE, "wwcx-network-sensor-suricata.service")
        self.assertEqual(
            str(MODULE.EVE),
            "/var/log/wwcx-network-sensor/suricata/eve.json",
        )
        self.assertEqual(
            MODULE.SURICATA_SOURCE_RELEASE,
            "edge1-suricata-sensor-consolidation-r1",
        )

    def test_normalize_alert_retains_allowlist(self):
        normalized = MODULE.normalize_suricata_alert(self.representative_event())
        self.assertEqual(normalized["source_port"], 53001)
        self.assertEqual(normalized["destination_port"], 443)
        self.assertEqual(normalized["application_protocol"], "tls")
        self.assertEqual(normalized["signature_id"], 2030001)
        self.assertEqual(normalized["generator_id"], 1)
        self.assertEqual(normalized["revision"], 4)
        self.assertEqual(normalized["flow_id"], 123456789)
        self.assertEqual(normalized["protocol"], "TCP")
        self.assertEqual(normalized["action"], "allowed")

    def test_normalize_alert_excludes_raw_material(self):
        normalized = MODULE.normalize_suricata_alert(self.representative_event())
        forbidden = {
            "payload",
            "payload_printable",
            "packet",
            "raw_event",
            "credentials",
            "private_key",
            "alert",
            "metadata",
        }
        self.assertTrue(forbidden.isdisjoint(normalized))
        serialized = json.dumps(normalized)
        self.assertNotIn("must-not-leave-eve", serialized)

    def test_invalid_numeric_fields_are_not_published(self):
        event = self.representative_event()
        event["src_port"] = 0
        event["dest_port"] = 70000
        event["flow_id"] = -1
        event["alert"]["signature_id"] = -10
        normalized = MODULE.normalize_suricata_alert(event)
        self.assertIsNone(normalized["source_port"])
        self.assertIsNone(normalized["destination_port"])
        self.assertIsNone(normalized["flow_id"])
        self.assertIsNone(normalized["signature_id"])

    def test_suricata_snapshot_is_bounded_private_and_identified(self):
        with tempfile.TemporaryDirectory() as directory:
            eve = pathlib.Path(directory) / "eve.json"
            rows = []
            for index in range(120):
                event = self.representative_event()
                event["timestamp"] = f"2026-07-29T08:25:{index % 60:02d}+00:00"
                event["flow_id"] = index + 1
                rows.append(json.dumps(event))
            rows.insert(0, json.dumps({"event_type": "flow", "payload": "ignored"}))
            eve.write_text("\n".join(rows) + "\n", encoding="utf-8")

            snapshot = MODULE.suricata(eve)
            self.assertTrue(snapshot["available"])
            self.assertEqual(snapshot["service"], MODULE.SURICATA_SERVICE)
            self.assertEqual(snapshot["source_path"], str(eve))
            self.assertEqual(snapshot["source_release"], MODULE.SURICATA_SOURCE_RELEASE)
            self.assertEqual(snapshot["alert_schema"], MODULE.SURICATA_ALERT_SCHEMA)
            self.assertEqual(len(snapshot["recent_alerts"]), 100)
            self.assertFalse(snapshot["privacy"]["packet_payloads_included"])
            self.assertFalse(snapshot["privacy"]["raw_events_included"])
            self.assertEqual(snapshot["recent_alerts"][-1]["flow_id"], 120)

    def test_non_alert_event_is_ignored(self):
        self.assertIsNone(MODULE.normalize_suricata_alert({"event_type": "flow"}))


if __name__ == "__main__":
    unittest.main()
