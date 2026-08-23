from __future__ import annotations
import json
import pathlib
import unittest
from server import ava_operator_policy as policy

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config/ava-operator-parity.json").read_text())

class AvaOperatorPolicyTests(unittest.TestCase):
    def test_policy_enables_authenticated_operator_parity(self):
        self.assertTrue(CONFIG["execution_enabled"])
        self.assertEqual(CONFIG["hosts"]["edge1"]["transport"], "edge1-agent-shell")
        self.assertEqual(CONFIG["hosts"]["business159"]["transport"], "business159-live-shell")

    def test_reads_are_standing_authority(self):
        for name in ("edge1.read.health", "edge1.read.services", "business159.read.health", "business159.read.git"):
            decision = policy.authorize(name, policy=CONFIG)
            self.assertTrue(decision["allowed"], name)
            self.assertFalse(decision["requires_confirmation"], name)

    def test_routine_repair_and_filesystem_are_allowed(self):
        self.assertTrue(policy.authorize("edge1.service.repair", policy=CONFIG)["allowed"])
        self.assertTrue(policy.authorize("business159.filesystem.stage", policy=CONFIG)["allowed"])

    def test_deploy_requires_confirmation(self):
        self.assertFalse(policy.authorize("edge1.deploy", policy=CONFIG)["allowed"])
        self.assertTrue(policy.authorize("edge1.deploy", confirmed=True, policy=CONFIG)["allowed"])
        self.assertFalse(policy.authorize("business159.deploy", policy=CONFIG)["allowed"])
        self.assertTrue(policy.authorize("business159.deploy", confirmed=True, policy=CONFIG)["allowed"])

    def test_raw_shell_is_attended_only(self):
        for name in ("edge1.shell.exec", "business159.shell.exec"):
            self.assertFalse(policy.authorize(name, policy=CONFIG)["allowed"])
            self.assertEqual(policy.authorize(name, policy=CONFIG)["classification"], "attended")
            self.assertTrue(policy.authorize(name, confirmed=True, policy=CONFIG)["allowed"])

    def test_restricted_and_unknown_fail_closed(self):
        for name in ("credential.rotate", "destructive.delete", "financial.pay", "unknown.magic"):
            self.assertFalse(policy.authorize(name, confirmed=True, policy=CONFIG)["allowed"], name)

if __name__ == "__main__":
    unittest.main()
