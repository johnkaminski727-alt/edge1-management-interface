from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server" / "suricata_protected_retention.py"
SPEC = importlib.util.spec_from_file_location("suricata_protected_retention", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def policy(root: Path, *, max_events: int = 100000, retention_days: int = 30) -> dict:
    return {
        "contract": "wwcx.suricata-protected-retention-policy.v1",
        "status": "implementation_ready",
        "enabled": True,
        "activation_requires_explicit_authorization": True,
        "authorization_record": "edge1-security-completion-20260730",
        "ingest": {
            "source": str(root / "latest.json"),
            "required_source_schema": "wwcx.suricata-source-alert.v1",
            "interval_seconds": 120,
            "max_alerts_per_run": 100,
            "deduplication": {
                "algorithm": "sha256",
                "unique_constraint": "event_key",
                "canonical_fields": ["timestamp", "signature", "signature_id", "generator_id", "revision", "flow_id", "event_id", "source", "source_port", "destination", "destination_port", "protocol", "application_protocol", "category", "action"],
            },
        },
        "storage": {
            "database": str(root / "private" / "alerts.sqlite3"),
            "status_file": str(root / "private" / "status.json"),
            "retention_days": retention_days,
            "max_database_bytes": 268435456,
            "max_events": max_events,
            "page_size_bytes": 4096,
            "max_page_count": 65536,
            "prune_target_percent": 90,
        },
        "privacy": {
            "approved_fields": ["timestamp", "signature", "severity", "risk", "category", "action", "source", "source_port", "destination", "destination_port", "protocol", "application_protocol", "signature_id", "generator_id", "revision", "flow_id", "event_id"]
        },
        "query": {"max_window_days": 7, "max_limit": 500},
        "acceptance": {"deployment_authorized": True},
    }


def alert(timestamp: str, event_id: str, **extra) -> dict:
    result = {
        "timestamp": timestamp,
        "signature": "Allowed test signature",
        "severity": 2,
        "category": "Attempted Information Leak",
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
        "flow_id": 77,
        "event_id": event_id,
    }
    result.update(extra)
    return result


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.policy_path = self.root / "policy.json"

    def tearDown(self):
        self.temp.cleanup()

    def write_policy(self, **kwargs):
        document = policy(self.root, **kwargs)
        self.policy_path.write_text(json.dumps(document), encoding="utf-8")
        return document

    def write_source(self, alerts, generated="2026-07-30T19:00:00+00:00"):
        source = {"generated_at": generated, "suricata": {"alert_schema": "wwcx.suricata-source-alert.v1", "generated_at": generated, "recent_alerts": alerts}}
        (self.root / "latest.json").write_text(json.dumps(source), encoding="utf-8")

    def test_ingest_is_deduplicated_private_atomic_and_integrity_checked(self):
        document = self.write_policy()
        self.write_source([alert("2026-07-30T18:59:00+00:00", "evt-1")])
        now = dt.datetime(2026, 7, 30, 19, 0, tzinfo=dt.timezone.utc)
        first = MODULE.ingest(self.policy_path, now=now)
        second = MODULE.ingest(self.policy_path, now=now + dt.timedelta(minutes=2))
        self.assertEqual(first["accepted_count"], 1)
        self.assertEqual(second["accepted_count"], 0)
        self.assertEqual(second["duplicate_count"], 1)
        self.assertTrue(second["integrity_ok"])
        database = Path(document["storage"]["database"])
        status_path = Path(document["storage"]["status_file"])
        self.assertEqual(stat.S_IMODE(database.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(database.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(status_path.stat().st_mode), 0o600)
        with sqlite3.connect(database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM alerts").fetchone()[0], 1)
            payload = connection.execute("SELECT payload_json FROM alerts").fetchone()[0]
        self.assertNotIn("packet", payload.lower())
        self.assertNotIn("raw", payload.lower())

    def test_unknown_and_nested_fields_are_rejected(self):
        self.write_policy()
        self.write_source([
            alert("2026-07-30T18:59:00+00:00", "evt-1", payload="forbidden"),
            alert("2026-07-30T18:59:01+00:00", "evt-2", category={"nested": True}),
        ])
        result = MODULE.ingest(self.policy_path, now=dt.datetime(2026, 7, 30, 19, 0, tzinfo=dt.timezone.utc))
        self.assertEqual(result["accepted_count"], 0)
        self.assertEqual(result["rejected_count"], 2)
        self.assertEqual(result["retained_count"], 0)

    def test_count_and_age_pruning_are_enforced(self):
        document = self.write_policy(max_events=2, retention_days=30)
        self.write_source([
            alert("2026-05-01T00:00:00+00:00", "old"),
            alert("2026-07-30T18:57:00+00:00", "one"),
            alert("2026-07-30T18:58:00+00:00", "two"),
            alert("2026-07-30T18:59:00+00:00", "three"),
        ])
        result = MODULE.ingest(self.policy_path, now=dt.datetime(2026, 7, 30, 19, 0, tzinfo=dt.timezone.utc))
        self.assertEqual(result["retained_count"], 2)
        self.assertGreaterEqual(result["pruned_count"], 2)
        with sqlite3.connect(document["storage"]["database"]) as connection:
            ids = [json.loads(row[0])["event_id"] for row in connection.execute("SELECT payload_json FROM alerts ORDER BY event_time")]
        self.assertEqual(ids, ["two", "three"])

    def test_missing_source_fails_closed_without_destroying_database(self):
        document = self.write_policy()
        self.write_source([alert("2026-07-30T18:59:00+00:00", "evt-1")])
        MODULE.ingest(self.policy_path, now=dt.datetime(2026, 7, 30, 19, 0, tzinfo=dt.timezone.utc))
        (self.root / "latest.json").unlink()
        result = MODULE.ingest(self.policy_path, now=dt.datetime(2026, 7, 30, 19, 2, tzinfo=dt.timezone.utc))
        self.assertEqual(result["state"], "source_unavailable")
        with sqlite3.connect(document["storage"]["database"]) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM alerts").fetchone()[0], 1)

    def test_event_key_is_stable_and_query_bounds_are_enforced(self):
        self.write_policy()
        item = MODULE.normalize_alert(alert("2026-07-30T18:59:00Z", "evt-1"), set(policy(self.root)["privacy"]["approved_fields"]))
        fields = policy(self.root)["ingest"]["deduplication"]["canonical_fields"]
        self.assertEqual(MODULE.event_key(item, fields), MODULE.event_key(dict(reversed(list(item.items()))), fields))
        with self.assertRaises(ValueError):
            MODULE.query(self.policy_path, 169, 1)
        with self.assertRaises(ValueError):
            MODULE.query(self.policy_path, 24, 501)

    def test_source_code_contains_no_raw_eve_or_public_history_path(self):
        text = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("/var/log/suricata", text)
        self.assertNotIn("/var/www", text)
        self.assertNotIn("socket.", text)


if __name__ == "__main__":
    unittest.main()
