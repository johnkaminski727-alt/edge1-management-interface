#!/usr/bin/env python3
"""Runtime tests for protected sanitized Suricata retention."""

from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import json
import os
import pathlib
import sqlite3
import stat
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server" / "suricata_protected_retention.py"
POLICY_PATH = ROOT / "config" / "security" / "suricata-protected-retention-policy.json"
SERVICE_PATH = ROOT / "deploy" / "systemd" / "wwcx-suricata-protected-retention.service"
TIMER_PATH = ROOT / "deploy" / "systemd" / "wwcx-suricata-protected-retention.timer"

spec = importlib.util.spec_from_file_location("suricata_protected_retention", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class SuricataProtectedRetentionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.policy["status"] = "implementation_ready"
        self.policy["enabled"] = True
        self.policy["acceptance"]["deployment_authorized"] = True
        self.policy["storage"]["database"] = str(self.root / "history" / "alerts.sqlite3")
        self.policy["storage"]["status_file"] = str(self.root / "history" / "status.json")
        self.policy["incident_promotion"]["evidence_root"] = str(self.root / "holds")
        self.policy_path = self.root / "policy.json"
        self.write_policy()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_policy(self) -> None:
        self.policy_path.write_text(json.dumps(self.policy), encoding="utf-8")

    def alert(self, **changes):
        alert = {
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "signature": "Test sanitized alert",
            "severity": 2,
            "risk": "medium",
            "category": "Test",
            "action": "allowed",
            "source": "192.0.2.10",
            "source_port": 12345,
            "destination": "198.51.100.20",
            "destination_port": 443,
            "protocol": "TCP",
            "application_protocol": "tls",
            "signature_id": 1001,
            "generator_id": 1,
            "revision": 1,
            "flow_id": 123456,
            "event_id": "event-1",
        }
        alert.update(changes)
        return alert

    def source(self, alerts):
        path = self.root / "latest.json"
        path.write_text(json.dumps({
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "security": {"alert_schema": "wwcx.suricata-source-alert.v1", "recent_alerts": alerts},
        }), encoding="utf-8")
        return path

    def test_committed_policy_is_disabled_and_runtime_does_not_create_database(self):
        disabled = copy.deepcopy(self.policy)
        disabled["enabled"] = False
        disabled["acceptance"]["deployment_authorized"] = False
        self.policy_path.write_text(json.dumps(disabled), encoding="utf-8")
        result = module.ingest(self.policy_path, self.source([self.alert()]))
        self.assertEqual(result["state"], "disabled")
        self.assertFalse(pathlib.Path(disabled["storage"]["database"]).exists())
        self.assertEqual(stat.S_IMODE(pathlib.Path(disabled["storage"]["status_file"]).stat().st_mode), 0o600)

    def test_ingestion_deduplicates_two_consecutive_snapshots(self):
        source = self.source([self.alert()])
        first = module.ingest(self.policy_path, source)
        second = module.ingest(self.policy_path, source)
        self.assertEqual(first["accepted"], 1)
        self.assertEqual(second["accepted"], 0)
        self.assertEqual(second["duplicate"], 1)
        self.assertEqual(second["retained"], 1)
        database = pathlib.Path(self.policy["storage"]["database"])
        self.assertEqual(stat.S_IMODE(database.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(database.parent.stat().st_mode), 0o700)

    def test_unknown_or_nested_fields_are_rejected(self):
        invalid = self.alert(payload={"secret": "not allowed"})
        result = module.ingest(self.policy_path, self.source([invalid]))
        self.assertEqual(result["accepted"], 0)
        self.assertEqual(result["rejected"], 1)
        self.assertEqual(result["retained"], 0)

    def test_source_schema_is_required(self):
        path = self.source([self.alert()])
        document = json.loads(path.read_text(encoding="utf-8"))
        document["security"]["alert_schema"] = "wrong"
        path.write_text(json.dumps(document), encoding="utf-8")
        result = module.ingest(self.policy_path, path)
        self.assertEqual(result["state"], "schema_rejected")
        self.assertFalse(pathlib.Path(self.policy["storage"]["database"]).exists())

    def test_event_key_is_stable_and_uses_explicit_nulls(self):
        alert = module.validate_alert(self.alert(application_protocol=None), self.policy)
        self.assertIsNotNone(alert)
        one = module.event_key(alert, self.policy)
        two = module.event_key(dict(reversed(list(alert.items()))), self.policy)
        self.assertEqual(one, two)
        self.assertEqual(len(one), 64)

    def test_query_is_bounded_and_read_only(self):
        module.ingest(self.policy_path, self.source([self.alert()]))
        database = pathlib.Path(self.policy["storage"]["database"])
        rows = module.query(self.policy_path, database, 24, 100)
        self.assertEqual(len(rows), 1)
        with self.assertRaises(ValueError):
            module.query(self.policy_path, database, 24 * 8, 100)
        with self.assertRaises(ValueError):
            module.query(self.policy_path, database, 24, 501)
        os.chmod(database, 0o644)
        with self.assertRaises(PermissionError):
            module.query(self.policy_path, database, 24, 100)

    def test_time_and_count_pruning(self):
        self.policy["storage"]["retention_days"] = 1
        self.policy["storage"]["max_events"] = 2
        self.write_policy()
        old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)).isoformat()
        alerts = [self.alert(timestamp=old, event_id="old"), self.alert(event_id="new-1"), self.alert(event_id="new-2"), self.alert(event_id="new-3")]
        result = module.ingest(self.policy_path, self.source(alerts))
        self.assertEqual(result["retained"], 2)
        self.assertGreaterEqual(result["pruned"], 2)

    def test_status_never_claims_control_plane_changes(self):
        result = module.ingest(self.policy_path, self.source([self.alert()]))
        for key in ("public_access", "network_listener", "raw_eve_accessed", "suricata_service_changed", "traffic_controls_changed"):
            self.assertIs(result[key], False)

    def test_units_are_root_only_non_networked_and_not_auto_enabled(self):
        service = SERVICE_PATH.read_text(encoding="utf-8")
        timer = TIMER_PATH.read_text(encoding="utf-8")
        self.assertIn("User=root", service)
        self.assertIn("UMask=0077", service)
        self.assertIn("RestrictAddressFamilies=AF_UNIX", service)
        self.assertIn("CapabilityBoundingSet=", service)
        self.assertNotIn("/var/log/suricata", service)
        self.assertNotIn("/var/www", service)
        self.assertIn("OnUnitActiveSec=120s", timer)
        self.assertNotIn("WantedBy=timers.target\n", service)

    def test_module_contains_no_raw_eve_or_network_server_path(self):
        text = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in ("/var/log/suricata", "eve.json", "socketserver", "http.server", "listen(", "subprocess", "systemctl"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
