#!/usr/bin/env python3
"""Validate the non-enforcing VPN access registration foundation."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.vpn_access_registration import RegistrationStore
from server.vpn_access_registration_exporter import export_payload, write_atomic


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value


class VpnAccessRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.db = Path(self.temporary.name) / "registration.sqlite3"
        self.clock = MutableClock()
        self.store = RegistrationStore(self.db, clock=self.clock)
        self.policy = self.store.create_policy(
            version="2026-07",
            title="VPN Privacy and Acceptable Use",
            notice="DNS filtering and eligible HTTP caching are disclosed here.",
            privacy_url="https://example.invalid/privacy",
            terms_url="https://example.invalid/terms",
            actor="admin",
        )
        self.peer_key = "A" * 43 + "="
        self.device = self.store.upsert_device(
            peer_public_key=self.peer_key,
            assigned_addresses=["10.77.0.50/32"],
            display_name="Test laptop",
            owner="Test owner",
            actor="wireguard-observer",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_new_device_is_pending_and_raw_key_is_not_stored(self) -> None:
        self.assertEqual(self.device["status"], "pending")
        self.assertEqual(self.device["assigned_addresses"], ["10.77.0.50/32"])
        with closing(sqlite3.connect(self.db)) as conn:
            stored = conn.execute("SELECT peer_key_sha256 FROM vpn_devices").fetchone()[0]
            dump = "\n".join(conn.iterdump())
        self.assertEqual(len(stored), 64)
        self.assertNotIn(self.peer_key, dump)

        observed_again = self.store.upsert_device(
            self.peer_key,
            ["10.77.0.50/32"],
            actor="wireguard-observer",
        )
        self.assertEqual(observed_again["display_name"], "Test laptop")
        self.assertEqual(observed_again["owner"], "Test owner")

    def test_acceptance_expires_after_thirty_days(self) -> None:
        acceptance = self.store.accept_policy(self.device["id"], actor="device-owner")
        self.assertEqual(
            acceptance["expires_at"],
            (self.clock.value + timedelta(days=30)).isoformat(),
        )
        self.assertEqual(self.store.get_device(self.device["id"])["status"], "registered")
        self.clock.value += timedelta(days=30, seconds=1)
        self.assertEqual(self.store.get_device(self.device["id"])["status"], "expired")

    def test_active_policy_versions_preserve_acceptance_history(self) -> None:
        self.store.accept_policy(self.device["id"], actor="device-owner")
        self.store.create_policy(
            version="2026-08",
            title="Revised VPN Terms",
            notice="Revised notice.",
            actor="admin",
        )
        self.assertEqual(
            self.store.get_device(self.device["id"])["status"],
            "policy_update_required",
        )
        latest = self.store.accept_policy(self.device["id"], actor="device-owner")
        policies = self.store.list_policies()
        self.assertEqual(latest["policy_id"], policies[0]["id"])
        self.assertEqual(self.store.get_device(self.device["id"])["status"], "registered")
        with closing(self.store.connect()) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM vpn_acceptance_records WHERE device_id=?",
                (self.device["id"],),
            ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_registration_exemption_can_expire_and_be_revoked(self) -> None:
        expiry = (self.clock.value + timedelta(days=2)).isoformat()
        exemption = self.store.add_exemption(
            self.device["id"],
            "registration",
            "Headless infrastructure",
            "admin",
            expires_at=expiry,
        )
        self.assertEqual(self.store.get_device(self.device["id"])["status"], "exempt")
        self.store.revoke_exemption(exemption["id"], actor="admin")
        self.assertEqual(self.store.get_device(self.device["id"])["status"], "pending")

        self.store.add_exemption(
            self.device["id"],
            "registration",
            "Temporary commissioning",
            "admin",
            expires_at=expiry,
        )
        self.clock.value += timedelta(days=3)
        self.assertEqual(self.store.get_device(self.device["id"])["status"], "pending")

    def test_policy_flags_and_quarantine_are_audited(self) -> None:
        updated = self.store.set_policy_flags(
            self.device["id"],
            {
                "cache_eligible": True,
                "proxy_required": True,
                "detailed_logging_permitted": False,
            },
            actor="admin",
        )
        self.assertTrue(updated["cache_eligible"])
        self.assertTrue(updated["proxy_required"])
        quarantined = self.store.set_quarantine(
            self.device["id"], True, actor="admin", reason="Security review"
        )
        self.assertEqual(quarantined["status"], "quarantined")
        cleared = self.store.set_quarantine(self.device["id"], False, actor="admin")
        self.assertEqual(cleared["status"], "pending")
        event_types = {event["event_type"] for event in self.store.audit_events()}
        self.assertIn("device.policy_flags_changed", event_types)
        self.assertIn("device.quarantined", event_types)
        self.assertIn("device.quarantine_cleared", event_types)

    def test_invalid_addresses_flags_and_exemptions_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.store.upsert_device("B" * 44, ["not-an-address"], actor="observer")
        with self.assertRaises(ValueError):
            self.store.set_policy_flags(
                self.device["id"], {"transparent_tls_interception": True}, actor="admin"
            )
        with self.assertRaises(ValueError):
            self.store.add_exemption(
                self.device["id"], "everything", "Too broad", "admin"
            )

    def test_export_is_privacy_limited_and_atomic(self) -> None:
        payload = export_payload(self.store)
        encoded = json.dumps(payload)
        self.assertFalse(payload["enforcement_active"])
        self.assertNotIn(self.peer_key, encoded)
        self.assertNotIn(self.device["peer_key_sha256"], encoded)
        self.assertNotIn(self.device["display_name"], encoded)

        output = Path(self.temporary.name) / "web" / "vpn-access-registration.json"
        write_atomic(output, payload)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), payload)
        self.assertFalse(output.with_name(f".{output.name}.tmp").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
