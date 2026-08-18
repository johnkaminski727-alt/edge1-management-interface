#!/usr/bin/env python3
"""Tests for cross-registry Mail Room configuration consistency."""

from __future__ import annotations

import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
CONFIG = ROOT / "config" / "messaging"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import mail_config_consistency as MODULE


class MailConfigConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.identities = json.loads((CONFIG / "mail-identities.json").read_text(encoding="utf-8"))
        cls.inbound = json.loads((CONFIG / "inbound-mail-hub.json").read_text(encoding="utf-8"))
        cls.outbound = json.loads((CONFIG / "outbound-mail-policy.json").read_text(encoding="utf-8"))
        cls.provider = json.loads((CONFIG / "mail-provider-inventory.json").read_text(encoding="utf-8"))

    def test_committed_registries_are_consistent(self) -> None:
        result = MODULE.validate(self.identities, self.inbound, self.outbound, self.provider)
        self.assertTrue(result["consistent"])
        self.assertEqual(result["canonical_source"], "config/messaging/mail-identities.json")
        self.assertEqual(result["domain_count"], 5)
        self.assertIn("john-inbox@ww.cx", result["internal_addresses"].values())
        self.assertIn("maildesk@ww.cx", result["internal_addresses"].values())

    def test_missing_inbound_domain_is_detected(self) -> None:
        inbound = copy.deepcopy(self.inbound)
        inbound["domains"].remove("omegafx.com")
        with self.assertRaisesRegex(MODULE.MailConfigConsistencyError, "registries disagree"):
            MODULE.validate(self.identities, inbound, self.outbound, self.provider)

    def test_extra_outbound_domain_is_detected(self) -> None:
        outbound = copy.deepcopy(self.outbound)
        outbound["delivery"]["allowed_from_domains"].append("unexpected.example")
        with self.assertRaisesRegex(MODULE.MailConfigConsistencyError, "registries disagree"):
            MODULE.validate(self.identities, self.inbound, outbound, self.provider)

    def test_provider_inventory_drift_is_detected(self) -> None:
        provider = copy.deepcopy(self.provider)
        provider["domains"].pop("scgardens.ca")
        with self.assertRaisesRegex(MODULE.MailConfigConsistencyError, "registries disagree"):
            MODULE.validate(self.identities, self.inbound, self.outbound, provider)

    def test_internal_mailbox_drift_is_detected(self) -> None:
        provider = copy.deepcopy(self.provider)
        provider["canonical_internal_addresses"]["shared_role_delivery_mailbox"] = "other@ww.cx"
        with self.assertRaisesRegex(MODULE.MailConfigConsistencyError, "internal addresses"):
            MODULE.validate(self.identities, self.inbound, self.outbound, provider)

    def test_route_outside_canonical_domains_is_detected(self) -> None:
        inbound = copy.deepcopy(self.inbound)
        inbound["routing"]["routes"]["role@unexpected.example"] = {
            "destination_type": "mailbox",
            "destination": "maildesk@ww.cx",
            "enabled": True,
        }
        with self.assertRaisesRegex(MODULE.MailConfigConsistencyError, "route outside"):
            MODULE.validate(self.identities, inbound, self.outbound, self.provider)


if __name__ == "__main__":
    unittest.main()
