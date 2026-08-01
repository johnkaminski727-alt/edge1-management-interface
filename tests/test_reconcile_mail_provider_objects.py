#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "messaging"
INBOUND_PATH = ROOT / "config" / "messaging" / "inbound-mail-hub.json"
IDENTITIES_PATH = ROOT / "config" / "messaging" / "mail-identities.json"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import reconcile_mail_provider_objects as MODULE


class ProviderObjectReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inbound = json.loads(INBOUND_PATH.read_text(encoding="utf-8"))
        cls.identities = json.loads(IDENTITIES_PATH.read_text(encoding="utf-8"))

    def complete_inventory(self) -> dict:
        routes = self.inbound["routing"]["routes"]
        objects = []
        for address, route in routes.items():
            access_class = (
                "private_john"
                if route["destination"] == "john-inbox@ww.cx"
                else "shared_role"
            )
            objects.append(
                {
                    "address": address,
                    "domain": address.rsplit("@", 1)[1],
                    "object_type": "forwarder",
                    "destinations": [route["destination"]],
                    "receives_mail": True,
                    "can_send": False,
                    "active": True,
                    "access_class": access_class,
                    "quota_bytes": None,
                    "notes": "Synthetic reconciliation fixture.",
                }
            )
        objects.extend(
            [
                {
                    "address": "john-inbox@ww.cx",
                    "domain": "ww.cx",
                    "object_type": "mailbox",
                    "destinations": [],
                    "receives_mail": True,
                    "can_send": False,
                    "active": True,
                    "access_class": "private_john",
                    "quota_bytes": None,
                    "notes": "Synthetic private mailbox.",
                },
                {
                    "address": "maildesk@ww.cx",
                    "domain": "ww.cx",
                    "object_type": "mailbox",
                    "destinations": [],
                    "receives_mail": True,
                    "can_send": False,
                    "active": True,
                    "access_class": "shared_role",
                    "quota_bytes": None,
                    "notes": "Synthetic shared mailbox.",
                },
                {
                    "address": "noreply@ww.cx",
                    "domain": "ww.cx",
                    "object_type": "system_account",
                    "destinations": [],
                    "receives_mail": False,
                    "can_send": False,
                    "active": True,
                    "access_class": "system",
                    "quota_bytes": None,
                    "notes": "Synthetic outbound-only system identity.",
                },
            ]
        )
        return {
            "contract": "wwcx.provider-mail-objects.v1",
            "provider_id": "synthetic-all-providers",
            "provider_family": "other",
            "captured_at": "2026-08-01T00:00:00+00:00",
            "source": {
                "method": "manual_export",
                "read_only": True,
                "evidence_files": ["synthetic.json"],
                "account_reference": None,
            },
            "objects": objects,
            "default_addresses": [
                {"domain": domain, "behavior": "reject", "destination": None}
                for domain in self.inbound["domains"]
            ],
            "domain_routing": [
                {"domain": domain, "mode": "local"}
                for domain in self.inbound["domains"]
            ],
        }

    def test_complete_inventory_is_ready_for_pilot(self) -> None:
        report = MODULE.reconcile(
            self.inbound,
            self.identities,
            [self.complete_inventory()],
        )
        self.assertEqual(report["summary"]["expected_route_count"], 37)
        self.assertEqual(report["summary"]["critical_gap_count"], 0)
        self.assertTrue(report["summary"]["ready_for_pilot"])
        self.assertEqual(
            {item["status"] for item in report["internal_mailboxes"]},
            {"present"},
        )

    def test_missing_expected_address_is_critical(self) -> None:
        inventory = self.complete_inventory()
        inventory["objects"] = [
            item
            for item in inventory["objects"]
            if item["address"] != "support@creekco.ca"
        ]
        report = MODULE.reconcile(self.inbound, self.identities, [inventory])
        self.assertFalse(report["summary"]["ready_for_pilot"])
        self.assertIn(
            "support@creekco.ca",
            next(
                gap["items"]
                for gap in report["critical_gaps"]
                if gap["type"] == "missing_expected_addresses"
            ),
        )

    def test_forwarder_destination_mismatch_is_critical(self) -> None:
        inventory = self.complete_inventory()
        item = next(
            value
            for value in inventory["objects"]
            if value["address"] == "accessibility@creekco.ca"
        )
        item["destinations"] = ["john-inbox@ww.cx"]
        report = MODULE.reconcile(self.inbound, self.identities, [inventory])
        mismatch = next(
            gap
            for gap in report["critical_gaps"]
            if gap["type"] == "forwarder_destination_mismatches"
        )
        self.assertEqual(mismatch["items"][0]["address"], "accessibility@creekco.ca")

    def test_forwarder_cycle_is_detected(self) -> None:
        inventory = self.complete_inventory()
        first = next(
            item for item in inventory["objects"] if item["address"] == "contact@creekco.ca"
        )
        second = next(
            item for item in inventory["objects"] if item["address"] == "support@creekco.ca"
        )
        first["destinations"] = ["support@creekco.ca"]
        second["destinations"] = ["contact@creekco.ca"]
        report = MODULE.reconcile(self.inbound, self.identities, [inventory])
        self.assertEqual(report["summary"]["forwarder_cycle_count"], 1)
        self.assertTrue(
            any(gap["type"] == "forwarder_cycles" for gap in report["critical_gaps"])
        )

    def test_unexpected_managed_address_and_catch_all_are_warnings(self) -> None:
        inventory = self.complete_inventory()
        inventory["objects"].append(
            {
                "address": "legacy@creekco.ca",
                "domain": "creekco.ca",
                "object_type": "mailbox",
                "destinations": [],
                "receives_mail": True,
                "can_send": True,
                "active": True,
                "access_class": "unknown",
                "quota_bytes": None,
                "notes": "Synthetic unexpected object.",
            }
        )
        default = next(
            item
            for item in inventory["default_addresses"]
            if item["domain"] == "creekco.ca"
        )
        default["behavior"] = "forward"
        default["destination"] = "maildesk@ww.cx"
        report = MODULE.reconcile(self.inbound, self.identities, [inventory])
        warning_types = {item["type"] for item in report["warnings"]}
        self.assertIn("unexpected_managed_addresses", warning_types)
        self.assertIn("non_reject_default_addresses", warning_types)

    def test_inventory_validation_rejects_address_domain_disagreement(self) -> None:
        inventory = self.complete_inventory()
        inventory["objects"][0]["domain"] = "example.com"
        with self.assertRaises(MODULE.InventoryError):
            MODULE.validate_inventory(inventory)

    def test_inventory_validation_rejects_non_read_only_source(self) -> None:
        inventory = self.complete_inventory()
        inventory["source"]["read_only"] = False
        with self.assertRaises(MODULE.InventoryError):
            MODULE.validate_inventory(inventory)


if __name__ == "__main__":
    unittest.main()
