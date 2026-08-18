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
IDENTITIES_PATH = ROOT / "config" / "messaging" / "mail-identities.json"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import inbound_mail_hub as MODULE
import mail_identity_registry


PRIVATE_DESTINATION = "john-inbox@ww.cx"
ROLE_DESTINATION = "maildesk@ww.cx"
SYSTEM_SENDER = "noreply@ww.cx"


class InboundMailHubTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.identities = json.loads(IDENTITIES_PATH.read_text(encoding="utf-8"))

    def active_config(self) -> dict:
        config = copy.deepcopy(self.config)
        config["enabled"] = True
        config["deployment_authorized"] = True
        config["production_routing_authorized"] = True
        config["ingress"]["selected"] = "provider_webhook"
        config["ingress"]["profiles"]["provider_webhook"]["enabled"] = True
        return config

    def test_committed_config_and_registry_are_disabled_and_safe(self) -> None:
        MODULE.validate_config(self.config)
        mail_identity_registry.validate_registry(self.identities)
        status = MODULE.status_payload(self.config)
        self.assertEqual(status["state"], "disabled")
        self.assertFalse(status["production_routing_enabled"])
        self.assertFalse(status["persist_raw_message"])
        self.assertFalse(status["persist_attachment_bytes"])
        self.assertTrue(status["managed_domain_catchall_enabled"])
        self.assertEqual(status["managed_domain_catchall_destination"], ROLE_DESTINATION)
        self.assertFalse(self.identities["outbound_activation_authorized"])
        self.assertEqual(self.identities["system_senders"]["noreply"]["address"], SYSTEM_SENDER)

    def test_multi_domain_inventory_and_route_count(self) -> None:
        status = MODULE.status_payload(self.config)
        self.assertEqual(
            set(status["domains"]),
            {"ww.cx", "creekco.ca", "spiritcreekgardens.com", "scgardens.ca", "omegafx.com"},
        )
        self.assertEqual(status["route_count"], 37)

    def test_private_and_role_destinations_are_real_and_distinct(self) -> None:
        rules = self.identities["rules"]
        self.assertEqual(rules["private_john_delivery_mailbox"], PRIVATE_DESTINATION)
        self.assertEqual(rules["shared_role_delivery_mailbox"], ROLE_DESTINATION)
        self.assertNotEqual(PRIVATE_DESTINATION, ROLE_DESTINATION)
        self.assertNotEqual(PRIVATE_DESTINATION, SYSTEM_SENDER)
        self.assertNotEqual(ROLE_DESTINATION, SYSTEM_SENDER)
        self.assertFalse(self.identities["mailboxes"]["private_john"]["accepts_direct_public_use"])
        self.assertFalse(self.identities["mailboxes"]["shared_role"]["accepts_direct_public_use"])

    def test_all_john_routes_use_private_destination(self) -> None:
        routes = self.config["routing"]["routes"]
        john_routes = {address: route for address, route in routes.items() if address.startswith("john@")}
        self.assertEqual(len(john_routes), 5)
        self.assertEqual(
            set(john_routes),
            {
                "john@ww.cx",
                "john@omegafx.com",
                "john@creekco.ca",
                "john@scgardens.ca",
                "john@spiritcreekgardens.com",
            },
        )
        self.assertTrue(all(route["destination"] == PRIVATE_DESTINATION for route in john_routes.values()))

    def test_all_non_john_explicit_routes_use_shared_role_destination(self) -> None:
        routes = self.config["routing"]["routes"]
        role_routes = {address: route for address, route in routes.items() if not address.startswith("john@")}
        self.assertEqual(len(role_routes), 32)
        self.assertTrue(all(route["destination"] == ROLE_DESTINATION for route in role_routes.values()))

    def test_verified_creekco_operational_identities_are_registered(self) -> None:
        routes = self.config["routing"]["routes"]
        mapping = self.identities["sender_selection"]["recipient_to_sender"]
        profiles = self.identities["sender_profiles"]
        expected = {
            "accessibility@creekco.ca": "creekco-accessibility",
            "noc@creekco.ca": "creekco-noc",
        }
        for address, profile_key in expected.items():
            with self.subTest(address=address):
                self.assertEqual(routes[address]["destination"], ROLE_DESTINATION)
                self.assertEqual(mapping[address], address)
                self.assertEqual(profiles[profile_key]["address"], address)
                self.assertEqual(profiles[profile_key]["status"], "verified_operational")
                self.assertFalse(profiles[profile_key]["outbound_enabled"])

    def test_enabled_config_requires_all_gates_and_catchall(self) -> None:
        for key in ("deployment_authorized", "production_routing_authorized"):
            candidate = self.active_config()
            candidate[key] = False
            with self.subTest(key=key):
                with self.assertRaises(MODULE.ConfigurationError):
                    MODULE.validate_config(candidate)
        candidate = self.active_config()
        candidate["routing"]["managed_domain_catchall"]["enabled"] = False
        with self.assertRaises(MODULE.ConfigurationError):
            MODULE.validate_config(candidate)

    def test_known_and_unknown_managed_recipients_route_correctly(self) -> None:
        envelope = MODULE.normalize_envelope(
            self.config,
            {
                "envelope_from": "sender@example.com",
                "recipients": [
                    "john@ww.cx",
                    "john@spiritcreekgardens.com",
                    "support@creekco.ca",
                    "accessibility@creekco.ca",
                    "noc@creekco.ca",
                    "records@spiritcreekgardens.com",
                    "anything-at-all@creekco.ca",
                    "new-role@omegafx.com",
                ],
                "message_size": 4096,
                "provider_message_id": "provider-id-1",
                "subject": "Test message",
            },
        )
        decisions = {item.recipient: item for item in MODULE.route_envelope(self.config, envelope)}
        self.assertEqual(decisions["john@ww.cx"].destination, PRIVATE_DESTINATION)
        self.assertEqual(decisions["john@spiritcreekgardens.com"].destination, PRIVATE_DESTINATION)
        self.assertEqual(decisions["support@creekco.ca"].destination, ROLE_DESTINATION)
        self.assertEqual(decisions["accessibility@creekco.ca"].destination, ROLE_DESTINATION)
        self.assertEqual(decisions["noc@creekco.ca"].destination, ROLE_DESTINATION)
        self.assertEqual(decisions["records@spiritcreekgardens.com"].destination, ROLE_DESTINATION)
        for address in ("anything-at-all@creekco.ca", "new-role@omegafx.com"):
            self.assertEqual(decisions[address].action, "route")
            self.assertEqual(decisions[address].destination, ROLE_DESTINATION)
            self.assertEqual(decisions[address].reason, "managed_domain_catchall")

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
            "recipients": ["unexpected-local-part@spiritcreekgardens.com"],
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
        self.assertEqual(result["event"]["decisions"][0]["reason"], "managed_domain_catchall")
        self.assertEqual(len(result["event"]["provider_message_id_sha256"]), 64)

    def test_limits_and_jsonl_reader(self) -> None:
        with self.assertRaises(MODULE.InboundHubError):
            MODULE.normalize_envelope(
                self.config,
                {
                    "envelope_from": "sender@example.com",
                    "recipients": ["john@ww.cx"],
                    "message_size": self.config["limits"]["max_message_bytes"] + 1,
                    "provider_message_id": "provider-id-5",
                },
            )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "audit.jsonl"
            path.write_text("bad\n" + json.dumps({"event": "one"}) + "\n", encoding="utf-8")
            self.assertEqual(MODULE.read_events(path, 10), [{"event": "one"}])


if __name__ == "__main__":
    unittest.main()
