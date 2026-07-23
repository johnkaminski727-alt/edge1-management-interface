#!/usr/bin/env python3
"""Tests for the Telegraph administration, observability, and queue stack."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reference.telegraph_admin_api import ALL_SCOPES, TokenAuthenticator
from reference.telegraph_control_plane import TelegraphControlPlane
from reference.telegraph_observability import TelegraphObservability
from reference.telegraph_store_forward import TelegraphStoreForwardQueue


class TokenAuthenticatorTests(unittest.TestCase):
    def test_authenticates_known_token_and_enforces_scopes(self) -> None:
        authenticator = TokenAuthenticator({
            "correct-horse-battery-staple": (
                "operator@example.invalid",
                {"telegraph.dashboard.read", "telegraph.alerts.acknowledge"},
            )
        })

        principal = authenticator.authenticate("Bearer correct-horse-battery-staple")

        self.assertIsNotNone(principal)
        assert principal is not None
        self.assertEqual(principal.subject, "operator@example.invalid")
        self.assertTrue(principal.permits("telegraph.dashboard.read"))
        self.assertFalse(principal.permits("telegraph.queue.cancel"))
        self.assertIsNone(authenticator.authenticate("Bearer incorrect"))
        self.assertIsNone(authenticator.authenticate(None))

    def test_environment_configuration_rejects_unknown_scope(self) -> None:
        document = [{"token": "test", "subject": "operator", "scopes": ["telegraph.root"]}]
        with patch.dict(os.environ, {"TELEGRAPH_ADMIN_TOKENS_JSON": json.dumps(document)}):
            with self.assertRaisesRegex(ValueError, "unknown scopes"):
                TokenAuthenticator.from_environment()

    def test_environment_configuration_accepts_every_documented_scope(self) -> None:
        document = [{"token": "test", "subject": "operator", "scopes": sorted(ALL_SCOPES)}]
        with patch.dict(os.environ, {"TELEGRAPH_ADMIN_TOKENS_JSON": json.dumps(document)}):
            principal = TokenAuthenticator.from_environment().authenticate("Bearer test")
        self.assertIsNotNone(principal)
        assert principal is not None
        self.assertEqual(principal.scopes, frozenset(ALL_SCOPES))


class AdministrationStackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.queue = TelegraphStoreForwardQueue(root / "queue.sqlite3", "office-a")
        self.observability = TelegraphObservability(root / "observability.sqlite3", "office-a")

    def tearDown(self) -> None:
        self.observability.close()
        self.queue.close()
        self.temporary.cleanup()

    def test_dashboard_composes_queue_peer_route_alert_and_event_state(self) -> None:
        envelope = {
            "message_id": "message-1",
            "origin": "office-a",
            "destination": "office-b",
            "payload": {"ciphertext": "not-inspected"},
        }
        self.assertTrue(
            self.queue.enqueue(
                envelope,
                destination="office-b",
                expires_at=2_000_000_000,
                priority="urgent",
                now=1_900_000_000,
            )
        )
        self.observability.record_event(
            source="test",
            event_type="message_queued",
            summary="A message entered the store-and-forward queue",
            message_id="message-1",
            detail={"token": "must-not-leak", "payload": "must-not-leak"},
            recorded_at=1_900_000_001,
        )
        queue_summary = self.observability.queue_summary(self.queue.connection)
        peer_summary = self.observability.peer_summary(TelegraphControlPlane("office-a").snapshot())
        route_summary = self.observability.route_summary([
            {
                "result": "selected",
                "selected_path": {"hop_count": 2, "estimated_latency_ms": 75},
            }
        ])
        self.observability.evaluate_alerts(
            queue_summary,
            peer_summary,
            queue_capacity_messages=1,
            now=1_900_000_002,
        )

        dashboard = self.observability.dashboard_snapshot(
            queue_summary,
            peer_summary,
            route_summary,
            now=1_900_000_003,
        )

        self.assertEqual(dashboard["office_id"], "office-a")
        self.assertEqual(dashboard["queue"]["active_messages"], 1)
        self.assertEqual(dashboard["routing"]["selected"], 1)
        self.assertEqual(dashboard["routing"]["average_hops"], 2.0)
        self.assertEqual(dashboard["overall_status"], "critical")
        self.assertEqual(dashboard["alerts"][0]["alert_key"], "queue.capacity")
        self.assertEqual(dashboard["recent_events"][0]["detail"]["token"], "[redacted]")
        self.assertEqual(dashboard["recent_events"][0]["detail"]["payload"], "[redacted]")

    def test_alert_acknowledgement_and_resolution_are_persistent(self) -> None:
        queue_summary = {
            "active_messages": 10,
            "active_bytes": 0,
            "states": {},
            "priorities": {},
            "retry_wait_messages": 0,
            "maximum_attempt_count": 0,
        }
        peers = {"peer_count": 0, "status_counts": {}, "lowest_health": [], "quarantine_recommendations": []}
        self.observability.evaluate_alerts(queue_summary, peers, queue_capacity_messages=10, now=100)
        self.observability.acknowledge_alert("queue.capacity", "operator", now=101)

        active = self.observability.alerts("active")
        self.assertEqual(active[0]["acknowledged_by"], "operator")
        self.assertEqual(active[0]["acknowledged_at"], 101)

        queue_summary["active_messages"] = 0
        self.observability.evaluate_alerts(queue_summary, peers, queue_capacity_messages=10, now=102)
        resolved = self.observability.alerts("resolved")
        self.assertEqual(resolved[0]["alert_key"], "queue.capacity")
        self.assertEqual(resolved[0]["last_seen_at"], 102)

    def test_diagnostic_bundle_redacts_nested_sensitive_fields(self) -> None:
        dashboard = {
            "message": {
                "payload": "secret body",
                "nested": {"private_key": "private material", "safe": "visible"},
            }
        }
        bundle = self.observability.diagnostic_bundle(
            dashboard,
            configuration={"authorization": "Bearer secret", "endpoint": "loopback"},
            now=123,
        )

        self.assertFalse(bundle["privacy"]["message_payloads_included"])
        self.assertEqual(bundle["dashboard"]["message"]["payload"], "[redacted]")
        self.assertEqual(bundle["dashboard"]["message"]["nested"]["private_key"], "[redacted]")
        self.assertEqual(bundle["dashboard"]["message"]["nested"]["safe"], "visible")
        self.assertEqual(bundle["configuration"]["authorization"], "[redacted]")


if __name__ == "__main__":
    unittest.main()
