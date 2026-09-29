#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy/control-center/install-contacts-ava-authenticated-ingress.sh"
CONTACTS_APP = ROOT / "src/web/contacts/app.js"
AVA_APP = ROOT / "src/web/ava-office/app.js"
REGISTRY = ROOT / "config/edge1_operator/navigation_registry.json"
AVA_POLICY = ROOT / "config/ava-operator-parity.json"


class ContactsAvaAuthenticatedIngressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.installer = INSTALLER.read_text(encoding="utf-8")
        cls.contacts = CONTACTS_APP.read_text(encoding="utf-8")
        cls.ava = AVA_APP.read_text(encoding="utf-8")
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.ava_policy = json.loads(AVA_POLICY.read_text(encoding="utf-8"))

    def test_browser_data_paths_use_authenticated_namespace(self):
        self.assertIn("/edge1-ops/contacts-api/", self.contacts)
        self.assertNotIn('"/api/contacts/', self.contacts)
        self.assertIn("/edge1-ops/ava-api/", self.ava)
        self.assertNotIn("'/api/ava-office/", self.ava)

    def test_candidate_pages_are_session_protected_and_get_only(self):
        for route in (
            "location ^~ /edge1-ops/contacts/",
            "location ^~ /edge1-ops/contacts-api/",
            "location ^~ /edge1-ops/ava/",
            "location ^~ /edge1-ops/ava-api/",
        ):
            self.assertIn(route, self.installer)
        self.assertGreaterEqual(
            self.installer.count("auth_request /_edge1_status_session_check;"),
            4,
        )
        self.assertGreaterEqual(
            self.installer.count("limit_except GET { deny all; }"),
            4,
        )

    def test_candidate_routes_are_not_prematurely_live(self):
        by_id = {item["id"]: item for item in self.registry["modules"]}
        contacts = by_id["contacts-relationships"]
        ava = by_id["ava-agent"]
        self.assertEqual(contacts["candidate_route"], "/edge1-ops/contacts/")
        self.assertIsNone(contacts["browser_route"])
        self.assertNotEqual(contacts["availability"], "accepted_live")
        self.assertEqual(ava["candidate_route"], "/edge1-ops/ava/")
        self.assertIsNone(ava["browser_route"])
        self.assertNotEqual(ava["availability"], "accepted_live")

    def test_ava_execution_gates_are_not_changed_by_browser_ingress(self):
        text = json.dumps(self.ava_policy, sort_keys=True)
        self.assertIn("confirmation", text.lower())
        self.assertIn("blocked", text.lower())
        self.assertNotIn("browser_route", self.ava_policy)
        self.assertIn("operator action/shell gates remain independent", self.installer)


if __name__ == "__main__":
    unittest.main()
