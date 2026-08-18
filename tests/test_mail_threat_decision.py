#!/usr/bin/env python3
"""Tests for normalized Mail Room threat decisions."""

from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
POLICY_PATH = ROOT / "config" / "messaging" / "mail-threat-policy.json"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import mail_threat_decision as MODULE


class MailThreatDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def clean_facts(self) -> dict:
        return {
            "scan_results": [
                {
                    "engine": "synthetic-clamav",
                    "engine_version": "1.0",
                    "ruleset_version": "test-db-1",
                    "state": "clean",
                    "reason_codes": [],
                }
            ],
            "authentication": {
                "spf": "pass",
                "dkim": "pass",
                "dmarc": "pass",
                "arc": "pass",
            },
            "phishing_risk": "none",
            "bec_risk": "none",
            "spam_risk": "low",
            "ai_risk": "low",
        }

    def test_clean_normalized_facts_can_deliver(self) -> None:
        result = MODULE.evaluate(self.policy, self.clean_facts())
        self.assertEqual(result["disposition"], "deliver")
        self.assertFalse(result["hard_security_block"])
        self.assertTrue(result["scan_complete"])

    def test_required_scan_missing_fails_closed(self) -> None:
        facts = self.clean_facts()
        facts["scan_results"] = []
        result = MODULE.evaluate(self.policy, facts)
        self.assertEqual(result["disposition"], "quarantine")
        self.assertTrue(result["hard_security_block"])
        self.assertIn("required_scan_missing", result["reason_codes"])

    def test_every_nonclean_scan_state_quarantines(self) -> None:
        for state in (
            "infected", "suspicious", "unscannable", "scan_error", "not_scanned"
        ):
            with self.subTest(state=state):
                facts = self.clean_facts()
                facts["scan_results"][0]["state"] = state
                result = MODULE.evaluate(self.policy, facts)
                self.assertEqual(result["disposition"], "quarantine")
                self.assertTrue(result["hard_security_block"])

    def test_dmarc_failure_is_hard_block(self) -> None:
        facts = self.clean_facts()
        facts["authentication"]["dmarc"] = "fail"
        result = MODULE.evaluate(self.policy, facts)
        self.assertEqual(result["disposition"], "quarantine")
        self.assertTrue(result["hard_security_block"])
        self.assertIn("dmarc_fail", result["reason_codes"])

    def test_ai_low_risk_cannot_downgrade_infected_scan(self) -> None:
        facts = self.clean_facts()
        facts["scan_results"][0]["state"] = "infected"
        facts["ai_risk"] = "none"
        result = MODULE.evaluate(self.policy, facts)
        self.assertEqual(result["disposition"], "quarantine")
        self.assertTrue(result["hard_security_block"])
        self.assertFalse(result["ai_may_reduce_hard_security_risk"])

    def test_ai_high_risk_may_escalate_otherwise_clean_message(self) -> None:
        facts = self.clean_facts()
        facts["ai_risk"] = "high"
        result = MODULE.evaluate(self.policy, facts)
        self.assertEqual(result["disposition"], "quarantine")
        self.assertFalse(result["hard_security_block"])
        self.assertIn("ai_risk_high", result["reason_codes"])

    def test_high_phishing_and_bec_risk_are_hard_blocks(self) -> None:
        for field in ("phishing_risk", "bec_risk"):
            with self.subTest(field=field):
                facts = self.clean_facts()
                facts[field] = "critical"
                result = MODULE.evaluate(self.policy, facts)
                self.assertEqual(result["disposition"], "quarantine")
                self.assertTrue(result["hard_security_block"])


if __name__ == "__main__":
    unittest.main()
