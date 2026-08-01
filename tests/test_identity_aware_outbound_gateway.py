#!/usr/bin/env python3

from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
CONFIG_PATH = ROOT / "config" / "messaging" / "outbound-mail-gateway.json"
POLICY_PATH = ROOT / "config" / "messaging" / "outbound-mail-policy.json"
IDENTITIES_PATH = ROOT / "config" / "messaging" / "mail-identities.json"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import identity_aware_outbound_gateway as MODULE
import mail_identity_registry
import outbound_mail_gateway


class IdentityAwareOutboundGatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.identities = json.loads(IDENTITIES_PATH.read_text(encoding="utf-8"))

    def base_payload(self) -> dict:
        return {
            "to": "recipient@example.com",
            "subject": "Identity-aware preview",
            "body": "This message is previewed but not sent.",
            "message_class": "business_correspondence",
            "signer_name": "John Kaminski",
            "signer_title": "Authorized Representative",
            "mailing_address": "151 2 Street South, Invermay, SK",
        }

    def test_status_exposes_safe_sender_selection_configuration(self) -> None:
        status = MODULE.status_payload(self.config, self.policy, self.identities)
        selection = status["sender_selection"]
        self.assertTrue(selection["automatic_selection_enabled"])
        self.assertFalse(selection["allow_submitted_from_override"])
        self.assertEqual(selection["private_delivery_mailbox"], "john-inbox@ww.cx")
        self.assertEqual(selection["shared_delivery_mailbox"], "maildesk@ww.cx")
        self.assertEqual(selection["system_sender"], "noreply@ww.cx")
        self.assertEqual(selection["live_sender_count"], 0)
        self.assertNotIn(
            "noreply@ww.cx",
            {item["address"] for item in selection["identities"]},
        )

    def test_preview_replaces_arbitrary_from_with_original_recipient_identity(self) -> None:
        payload = self.base_payload()
        payload.update(
            {
                "from_address": "wrong@example.com",
                "reply_to": "wrong@example.com",
                "original_recipient": "john@spiritcreekgardens.com",
            }
        )
        preview = MODULE.compose_preview(
            self.config,
            self.policy,
            self.identities,
            payload,
        )
        self.assertEqual(preview["request"]["from_address"], "john@spiritcreekgardens.com")
        self.assertEqual(preview["request"]["reply_to"], "john@spiritcreekgardens.com")
        self.assertEqual(preview["sender_selection"]["reason"], "original_recipient")
        self.assertTrue(preview["sender_selection"]["from_address_replaced"])
        self.assertEqual(preview["audit_record"]["from_address"], "john@spiritcreekgardens.com")
        self.assertIn("Email: john@spiritcreekgardens.com", preview["body"])
        self.assertNotIn("wrong@example.com", json.dumps(preview))

    def test_preview_selects_role_identity(self) -> None:
        payload = self.base_payload()
        payload["original_recipient"] = "records@spiritcreekgardens.com"
        preview = MODULE.compose_preview(
            self.config,
            self.policy,
            self.identities,
            payload,
        )
        self.assertEqual(preview["request"]["from_address"], "records@spiritcreekgardens.com")
        self.assertEqual(preview["request"]["reply_to"], "records@spiritcreekgardens.com")
        self.assertEqual(preview["audit_record"]["from_address"], "records@spiritcreekgardens.com")
        self.assertIn("Email: records@spiritcreekgardens.com", preview["body"])

    def test_system_preview_uses_noreply(self) -> None:
        payload = self.base_payload()
        payload["system_generated"] = True
        preview = MODULE.compose_preview(
            self.config,
            self.policy,
            self.identities,
            payload,
        )
        self.assertEqual(preview["request"]["from_address"], "noreply@ww.cx")
        self.assertIsNone(preview["request"]["reply_to"])
        self.assertEqual(preview["sender_selection"]["reason"], "system_generated")
        self.assertEqual(preview["audit_record"]["from_address"], "noreply@ww.cx")
        self.assertIn("Email: noreply@ww.cx", preview["body"])

    def test_noreply_cannot_be_selected_by_manual_hint(self) -> None:
        for hint in ("system-noreply", "noreply@ww.cx"):
            payload = self.base_payload()
            payload["identity_hint"] = hint
            with self.subTest(hint=hint):
                with self.assertRaises(mail_identity_registry.IdentitySelectionError):
                    MODULE.compose_preview(
                        self.config,
                        self.policy,
                        self.identities,
                        payload,
                    )

    def test_live_send_is_blocked_until_selected_identity_is_authorized(self) -> None:
        payload = self.base_payload()
        payload["original_recipient"] = "john@ww.cx"
        with self.assertRaises(outbound_mail_gateway.DeliveryDisabledError):
            MODULE.send_message(
                self.config,
                self.policy,
                self.identities,
                payload,
                confirmation=True,
            )


if __name__ == "__main__":
    unittest.main()
