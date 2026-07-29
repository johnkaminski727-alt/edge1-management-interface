#!/usr/bin/env python3
"""Validation for the read-only security correlation exporter."""

import json
import tempfile
import unittest
from pathlib import Path

from server.security_correlation_exporter import build_snapshot, write_snapshot


class SecurityCorrelationTests(unittest.TestCase):
    def write_json(self, folder, name, value):
        path = folder / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_high_confidence_correlation_from_multiple_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            security = self.write_json(root, "security.json", {
                "recent_alerts": [{
                    "timestamp": "2026-07-29T00:00:00Z",
                    "signature": "Suspicious traffic",
                    "source": "10.0.0.5",
                    "destination": "8.8.8.8",
                    "severity": "high"
                }]
            })
            operations = self.write_json(root, "operations.json", {
                "dns_queries": [{
                    "timestamp": "2026-07-29T00:00:10Z",
                    "client": "10.0.0.5",
                    "query": "bad.example"
                }],
                "firewall_events": [{
                    "timestamp": "2026-07-29T00:00:20Z",
                    "source": "10.0.0.5",
                    "action": "blocked"
                }]
            })
            network = self.write_json(root, "network.json", {})
            spamhaus = root / "spamhaus.txt"
            spamhaus.write_text("combined4=10\ndrop6=2\n", encoding="utf-8")

            result = build_snapshot(security, network, operations, spamhaus)

            self.assertEqual(result["summary"]["event_count"], 3)
            self.assertEqual(result["summary"]["high_confidence_count"], 1)
            self.assertTrue(result["correlations"])

    def test_missing_sources_are_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = build_snapshot(
                root / "missing-security.json",
                root / "missing-network.json",
                root / "missing-operations.json",
                root / "missing-spamhaus.txt",
            )
            self.assertGreater(len(result["warnings"]), 0)
            self.assertTrue(result["read_only"])

    def test_privacy_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            empty = root / "empty.json"
            empty.write_text("{}", encoding="utf-8")
            spamhaus = root / "spamhaus.txt"
            spamhaus.write_text("combined4=1\n", encoding="utf-8")
            result = build_snapshot(empty, empty, empty, spamhaus)
            self.assertFalse(result["privacy"]["packet_payloads_included"])
            self.assertFalse(result["privacy"]["credentials_included"])

    def test_atomic_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "result.json"
            write_snapshot({"ok": True}, output)
            self.assertEqual(json.loads(output.read_text())["ok"], True)
            self.assertFalse(output.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
