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
CONFIG_PATH = ROOT / "config" / "messaging" / "outbound-mail-gateway.json"
POLICY_PATH = ROOT / "config" / "messaging" / "outbound-mail-policy.json"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import outbound_mail_gateway as MODULE
import outbound_mail_policy


class OutboundMailGatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def test_committed_gateway_is_disabled_and_provider_neutral(self) -> None:
        MODULE.validate_gateway_config(self.config)
        self.assertFalse(self.config["enabled"])
        self.assertFalse(self.config["external_delivery_authorized"])
        self.assertFalse(self.config["admin"]["send_endpoint_enabled"])
        self.assertEqual(self.config["provider"]["selected"], "none")
        self.assertIn("smtp_submission", self.config["provider"]["profiles"])
        self.assertIn("gmail_api", self.config["provider"]["profiles"])
        self.assertIn("internal_webhook", self.config["provider"]["profiles"])
        self.assertFalse(self.config["content"]["persist_message_bodies"])
        self.assertFalse(self.config["content"]["persist_attachment_bytes"])

    def test_status_reports_preview_mode_and_no_external_delivery(self) -> None:
        status = MODULE.status_payload(self.config, self.policy)
        self.assertEqual(status["gateway"], "wwcx-outbound-mail-gateway")
        self.assertEqual(status["state"], "disabled")
        self.assertTrue(status["preview_enabled"])
        self.assertFalse(status["external_delivery_enabled"])
        self.assertFalse(status["hidden_open_tracking"])
        self.assertFalse(status["device_fingerprinting"])

    def test_preview_builds_footer_headers_and_disclosed_action_link(self) -> None:
        preview = MODULE.compose_preview(
            self.config,
            self.policy,
            {
                "from_address": "john@ww.cx",
                "to": "records@example.com; manager@example.com",
                "cc": "copy@example.com",
                "subject": "Records request",
                "body": "Please provide the requested records.",
                "message_class": "business_correspondence",
                "signer_name": "John Kaminski",
                "signer_title": "Authorized Representative",
                "case_id": "ENT-184366738",
                "action_id": "ENT-ACT-014",
                "mailing_address": "151 2 Street South, Invermay, SK",
            },
        )
        self.assertIn(outbound_mail_policy.FOOTER_MARKER, preview["body"])
        self.assertIn("Access to the linked correspondence record may be logged", preview["body"])
        self.assertIn("does not create confidentiality, privilege", preview["body"])
        self.assertEqual(preview["headers"]["X-WWCX-Case-ID"], "ENT-184366738")
        self.assertEqual(preview["headers"]["X-WWCX-Action-ID"], "ENT-ACT-014")
        self.assertTrue(preview["action_url"].startswith("https://ww.cx/correspondence/r/"))
        self.assertEqual(len(preview["action_token_sha256"]), 64)
        self.assertEqual(len(preview["request"]["recipients"]), 3)

    def test_send_is_blocked_before_provider_or_policy_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(MODULE.DeliveryDisabledError):
                MODULE.send_message(
                    self.config,
                    self.policy,
                    {
                        "to": "records@example.com",
                        "subject": "Records request",
                        "body": "Please provide the requested records.",
                        "mailing_address": "151 2 Street South, Invermay, SK",
                    },
                    confirmation=True,
                    audit_path=pathlib.Path(temp_dir) / "audit.jsonl",
                )
            self.assertFalse((pathlib.Path(temp_dir) / "audit.jsonl").exists())

    def test_confirmation_is_an_independent_send_gate(self) -> None:
        active_config = copy.deepcopy(self.config)
        active_config["enabled"] = True
        active_config["deployment_authorized"] = True
        active_config["external_delivery_authorized"] = True
        active_config["admin"]["send_endpoint_enabled"] = True
        active_config["provider"]["selected"] = "smtp_submission"
        active_config["provider"]["profiles"]["smtp_submission"]["enabled"] = True

        active_policy = outbound_mail_policy.activated_copy(
            self.policy, "151 2 Street South, Invermay, SK"
        )
        MODULE.validate_gateway_config(active_config)
        with self.assertRaises(MODULE.DeliveryDisabledError):
            MODULE.send_message(
                active_config,
                active_policy,
                {
                    "to": "records@example.com",
                    "subject": "Records request",
                    "body": "Please provide the requested records.",
                },
                confirmation=False,
            )

    def test_provider_status_never_exposes_runtime_secrets(self) -> None:
        smtp = self.config["provider"]["profiles"]["smtp_submission"]
        values = {
            smtp["host_env"]: "smtp.example.com",
            smtp["port_env"]: "587",
            smtp["username_env"]: "sender@example.com",
            smtp["password_env"]: "do-not-expose",
        }
        with mock.patch.dict(os.environ, values, clear=False):
            statuses = MODULE.provider_statuses(self.config)
        serialized = json.dumps([item.to_dict() for item in statuses])
        self.assertNotIn("do-not-expose", serialized)
        self.assertNotIn("sender@example.com", serialized)
        smtp_status = next(item for item in statuses if item.name == "smtp_submission")
        self.assertTrue(smtp_status.configured)
        self.assertFalse(smtp_status.ready)

    def test_commercial_preview_requires_unsubscribe_link(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.compose_preview(
                self.config,
                self.policy,
                {
                    "to": "recipient@example.com",
                    "subject": "Commercial notice",
                    "body": "A commercial message.",
                    "message_class": "commercial",
                    "mailing_address": "151 2 Street South, Invermay, SK",
                },
            )

    def test_audit_reader_ignores_invalid_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "audit.jsonl"
            path.write_text(
                "not-json\n" + json.dumps({"event": "one"}) + "\n" + json.dumps({"event": "two"}) + "\n",
                encoding="utf-8",
            )
            events = MODULE.read_audit_events(path, 10)
        self.assertEqual([item["event"] for item in events], ["two", "one"])

    def test_config_rejects_enabled_gateway_with_disabled_provider(self) -> None:
        candidate = copy.deepcopy(self.config)
        candidate["enabled"] = True
        candidate["deployment_authorized"] = True
        candidate["external_delivery_authorized"] = True
        candidate["admin"]["send_endpoint_enabled"] = True
        with self.assertRaises(MODULE.ConfigurationError):
            MODULE.validate_gateway_config(candidate)


if __name__ == "__main__":
    unittest.main()
