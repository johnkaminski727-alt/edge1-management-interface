#!/usr/bin/env python3
"""Policy checks for the BigBird Edge1 Control Plane v2 manifest."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "integrations/bigbird-edge1-control-plane/capabilities-v2.json"


class ControlPlaneV2PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.capabilities = cls.manifest["capabilities"]

    def test_version_and_identity(self):
        self.assertEqual(self.manifest["version"], 2)
        self.assertEqual(self.manifest["control_plane"], "bigbird-edge1")

    def test_capability_names_are_unique(self):
        names = [item["name"] for item in self.capabilities]
        self.assertEqual(len(names), len(set(names)))

    def test_enabled_mutations_are_forbidden_during_migration(self):
        if self.manifest["mode"] != "migration":
            self.skipTest("migration-only policy")
        enabled_mutations = [
            item["name"]
            for item in self.capabilities
            if item["enabled"] and item["class"] != "read"
        ]
        self.assertEqual(enabled_mutations, [])

    def test_mutations_have_explicit_policy(self):
        for item in self.capabilities:
            if item["class"] != "read":
                self.assertIn("mutation_policy", item, item["name"])
                self.assertNotEqual(item["mutation_policy"], "allow", item["name"])

    def test_apply_requires_stronger_scope_than_stage(self):
        by_name = {item["name"]: item for item in self.capabilities}
        stage = by_name["edge1.files.stage"]
        apply = by_name["edge1.files.apply"]
        self.assertNotEqual(stage["scope"], apply["scope"])
        self.assertTrue(apply["require_precondition"])
        self.assertTrue(apply["require_backup"])
        self.assertTrue(apply["require_post_apply_verification"])

    def test_no_generic_dangerous_capability_names(self):
        forbidden = {"shell", "sudo", "sql", "exec", "command", "arbitrary"}
        for item in self.capabilities:
            tokens = set(item["name"].replace("-", ".").split("."))
            self.assertFalse(tokens & forbidden, item["name"])


if __name__ == "__main__":
    unittest.main()
