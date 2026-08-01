#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
REGISTRY_PATH = ROOT / "config" / "messaging" / "mail-identities.json"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import mail_identity_registry as MODULE


class MailIdentityRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def test_registry_defines_distinct_mailboxes_and_system_sender(self) -> None:
        MODULE.validate_registry(self.registry)
        status = MODULE.status_payload(self.registry)
        self.assertEqual(status["private_delivery_mailbox"], "john-inbox@ww.cx")
        self.assertEqual(status["shared_delivery_mailbox"], "maildesk@ww.cx")
        self.assertEqual(status["system_sender"], "noreply@ww.cx")
        self.assertEqual(
            len(
                {
                    status["private_delivery_mailbox"],
                    status["shared_delivery_mailbox"],
                    status["system_sender"],
                }
            ),
            3,
        )
        self.assertFalse(status["allow_submitted_from_override"])
        self.assertFalse(status["outbound_activation_authorized"])
        self.assertEqual(status["live_sender_count"], 0)

    def test_original_recipient_selects_matching_private_sender(self) -> None:
        selection = MODULE.resolve_sender(
            self.registry,
            {
                "from_address": "wrong@example.com",
                "original_recipient": "john@spiritcreekgardens.com",
            },
        )
        self.assertEqual(selection.address, "john@spiritcreekgardens.com")
        self.assertEqual(selection.reason, "original_recipient")
        self.assertEqual(selection.reply_to, "john@spiritcreekgardens.com")
        self.assertTrue(selection.submitted_from_present)
        self.assertTrue(selection.from_address_replaced)
        self.assertFalse(selection.live_enabled)

    def test_original_recipient_selects_matching_role_sender(self) -> None:
        selection = MODULE.resolve_sender(
            self.registry,
            {"original_recipient": "support@creekco.ca"},
        )
        self.assertEqual(selection.address, "support@creekco.ca")
        self.assertEqual(selection.reason, "original_recipient")
        self.assertEqual(selection.reply_to, "support@creekco.ca")

    def test_reconciled_creekco_identities_select_themselves(self) -> None:
        expected = {
            "accessibility@creekco.ca": "creekco-accessibility",
            "noc@creekco.ca": "creekco-noc",
        }
        for address, profile_key in expected.items():
            with self.subTest(address=address):
                selection = MODULE.resolve_sender(
                    self.registry,
                    {"original_recipient": address},
                )
                self.assertEqual(selection.address, address)
                self.assertEqual(selection.identity_key, profile_key)
                self.assertEqual(selection.reason, "original_recipient")
                self.assertEqual(selection.reply_to, address)
                self.assertFalse(selection.live_enabled)

    def test_identity_hint_and_default_sender(self) -> None:
        hinted = MODULE.resolve_sender(
            self.registry,
            {"identity_hint": "creekco-regulatory"},
        )
        self.assertEqual(hinted.address, "regulatory@creekco.ca")
        self.assertEqual(hinted.reason, "identity_hint")
        defaulted = MODULE.resolve_sender(self.registry, {})
        self.assertEqual(defaulted.address, "john@ww.cx")
        self.assertEqual(defaulted.reason, "default_sender")

    def test_system_generated_mail_uses_noreply_without_reply_to(self) -> None:
        selection = MODULE.resolve_sender(
            self.registry,
            {"system_generated": True, "from_address": "john@ww.cx"},
        )
        self.assertEqual(selection.address, "noreply@ww.cx")
        self.assertEqual(selection.reason, "system_generated")
        self.assertIsNone(selection.reply_to)
        self.assertTrue(selection.from_address_replaced)

    def test_unknown_original_recipient_is_rejected(self) -> None:
        with self.assertRaises(MODULE.IdentitySelectionError):
            MODULE.resolve_sender(
                self.registry,
                {"original_recipient": "unknown@ww.cx"},
            )

    def test_registry_rejects_mailbox_or_noreply_collisions(self) -> None:
        candidate = copy.deepcopy(self.registry)
        candidate["mailboxes"]["private_john"]["address"] = "noreply@ww.cx"
        candidate["rules"]["private_john_delivery_mailbox"] = "noreply@ww.cx"
        with self.assertRaises(MODULE.IdentityConfigurationError):
            MODULE.validate_registry(candidate)


if __name__ == "__main__":
    unittest.main()
