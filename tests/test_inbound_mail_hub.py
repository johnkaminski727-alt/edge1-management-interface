#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
CONFIG_PATH = ROOT / "config" / "messaging" / "inbound-mail-hub.json"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import inbound_mail_hub as MODULE


class InboundMailHubTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def active_config(self) -> dict:
        config = copy.deepcopy(self.config)
        config["enabled"] = True
        config["deployment_authorized"] = True
        config["production_routing_authorized"] = True
        config["ingress"]["selected"] = "provider_webhook"
        config["ingress"]["profiles"]["provider_webhook"]["enabled"] = True
        return config

    def test_committed_config_is_disabled_and_safe(self) -> None:
        MODULE.validate_config(self.config)
        status = MODULE.status_payload(self.config)
        self.assertEqual(status["state"], "disabled")
        self.assertFalse(status["production_routing_enabled"])
        self.assertFalse(status["persist_raw_message"])
        self.assertFalse(status["persist_attachment_bytes"])
        self.assertEqual(self.config["routing"]["unknown_recipient_action"], "quarantine")

    def test_enabled_config_requires_all_gates(self) -> None:
        for key in ("deployment_authorized", "production_routing_authorized"):
            candidate = self.active_config()
            candidate[key] = False
            with self.subTest(key=key):
                with self.assertRaises(MODULE.ConfigurationError):
                    MODULE.validate_config(candidate)

    def test_known_recipient_routes_and_unknown_quarantines(self) -> None:
        envelope = MODULE.normalize_envelope(
            self.config,
            {
                "envelope_from": "sender@example.com",
                "recipients": ["john@ww.cx", "unknown@ww.cx"],
                "message_size": 4096,
                "provider_message_id": "provider-id-1",
                "subject": "Test message",
            },
        )
        decisions = MODULE.route_envelope(self.config, envelope)
        by_recipient = {item.recipient: item for item in decisions}
        self.assertEqual(by_recipient["john@ww.cx"].action, "route")
        self.assertEqual(by_recipient["john@ww.cx"].destination, "john@ww.cx")
        self.assertEqual(by_recipient["unknown@ww.cx"].action, "quarantine")

    def test_unmanaged_domain_is_rejected(self) -> None:
        envelope = MODULE.normalize_envelope(
            self.config,
            {
                "envelope_from": "sender@example.com",
                "recipients": ["victim@example.net"],
                "message_size": 100,
                "provider_message_id": "provider-id-2",
            },
        )
        decision = MODULE.route_envelope(self.config, envelope)[0]
        self.assertEqual(decision.action, "reject")
        self.assertEqual(decision.reason, "domain_not_managed")

    def test_processing_is_blocked_while_disabled(self) -> None:
        with self.assertRaises(MODULE.IngressDisabledError):
            MODULE.process_ingress(
                self.config,
                {
                    "envelope_from": "sender@example.com",
                    "recipients": ["john@ww.cx"],
                    "message_size": 100,
                    "provider_message_id": "provider-id-3",
                },
                "token",
            )

    def test_active_processing_requires_authentication_and_minimizes_audit(self) -> None:
        config = self.active_config()
        secret_env = config["ingress"]["profiles"]["provider_webhook"]["secret_env"]
        payload = {
            "envelope_from": "sender@example.com",
            "recipients": ["john@ww.cx"],
            "message_size": 100,
            "provider_message_id": "provider-id-4",
            "subject": "Sensitive subject",
            "body": "Sensitive body that must not enter audit output",
        }
        with mock.patch.dict(os.environ, {secret_env: "correct-token"}, clear=False):
            with self.assertRaises(MODULE.AuthenticationError):
                MODULE.process_ingress(config, payload, "wrong-token")
            result = MODULE.process_ingress(config, payload, "correct-token")
        serialized = json.dumps(result)
        self.assertTrue(result["accepted"])
        self.assertNotIn("provider-id-4", serialized)
        self.assertNotIn("Sensitive subject", serialized)
        self.assertNotIn("Sensitive body", serialized)
        self.assertEqual(len(result["event"]["provider_message_id_sha256"]), 64)

    def test_limits_are_enforced(self) -> None:
        payload = {
            "envelope_from": "sender@example.com",
            "recipients": ["john@ww.cx"],
            "message_size": self.config["limits"]["max_message_bytes"] + 1,
            "provider_message_id": "provider-id-5",
        }
        with self.assertRaises(MODULE.InboundHubError):
            MODULE.normalize_envelope(self.config, payload)

    def test_jsonl_reader_ignores_invalid_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "audit.jsonl"
            path.write_text("bad\n" + json.dumps({"event": "one"}) + "\n", encoding="utf-8")
            events = MODULE.read_events(path, 10)
        self.assertEqual(events, [{"event": "one"}])


if __name__ == "__main__":
    unittest.main()
