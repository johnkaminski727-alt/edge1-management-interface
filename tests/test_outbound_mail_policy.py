#!/usr/bin/env python3

from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server" / "outbound_mail_policy.py"
POLICY_PATH = ROOT / "config" / "messaging" / "outbound-mail-policy.json"

SPEC = importlib.util.spec_from_file_location("outbound_mail_policy", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class OutboundMailPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.now = dt.datetime(2026, 8, 1, 3, 30, tzinfo=dt.timezone.utc)

    def active_policy(self):
        return MODULE.activated_copy(self.policy, "151 2 Street South, Invermay, SK")

    def test_committed_policy_is_disabled_and_safe(self) -> None:
        MODULE.validate_policy(self.policy)
        self.assertFalse(self.policy["enabled"])
        self.assertFalse(self.policy["deployment_authorized"])
        self.assertFalse(self.policy["smtp_cutover_authorized"])
        self.assertFalse(self.policy["tracking"]["hidden_open_tracking"])
        self.assertFalse(self.policy["tracking"]["device_fingerprinting"])
        self.assertFalse(self.policy["tracking"]["collect_full_ip"])
        self.assertFalse(self.policy["audit"]["record_body"])
        self.assertFalse(self.policy["audit"]["record_action_token"])

    def test_enabled_policy_requires_all_activation_gates(self) -> None:
        for key in ("deployment_authorized", "smtp_cutover_authorized"):
            candidate = copy.deepcopy(self.policy)
            candidate["enabled"] = True
            candidate["organization"]["mailing_address"] = "151 2 Street South, Invermay, SK"
            candidate[key] = False
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    MODULE.validate_policy(candidate)

    def test_policy_rejects_covert_tracking_and_excess_collection(self) -> None:
        mutations = (
            lambda value: value["tracking"].update(hidden_open_tracking=True),
            lambda value: value["tracking"].update(device_fingerprinting=True),
            lambda value: value["tracking"].update(collect_full_ip=True),
            lambda value: value["audit"].update(record_body=True),
            lambda value: value["audit"].update(record_action_token=True),
            lambda value: value["audit"].update(record_action_token_hash=False),
        )
        for mutate in mutations:
            candidate = copy.deepcopy(self.policy)
            mutate(candidate)
            with self.subTest(mutate=mutate):
                with self.assertRaises(ValueError):
                    MODULE.validate_policy(candidate)

    def test_plain_text_composition_is_idempotent_and_disclosed(self) -> None:
        policy = self.active_policy()
        result = MODULE.compose_plain_text_message(
            policy,
            body="Hello Enterprise Team,\n\nPlease provide the requested records.",
            subject="Records request",
            recipients=["records@example.com", "Manager@Example.com"],
            signer_name="John Kaminski",
            signer_title="Authorized Representative",
            case_id="ENT-184366738",
            action_id="ENT-ACT-014",
            timestamp=self.now,
        )
        body = result["body"]
        self.assertIn(MODULE.FOOTER_MARKER, body)
        self.assertIn("Access to the linked correspondence record may be logged", body)
        self.assertIn("does not create confidentiality, privilege", body)
        self.assertNotIn(result["action_token"], json.dumps(result["audit_record"]))
        self.assertEqual(len(result["action_token_sha256"]), 64)
        self.assertEqual(result["headers"]["X-WWCX-Case-ID"], "ENT-184366738")
        self.assertEqual(result["headers"]["X-WWCX-Action-ID"], "ENT-ACT-014")
        second = MODULE.append_plain_text_footer(body, "ignored")
        self.assertEqual(second.count(MODULE.FOOTER_MARKER), 1)

    def test_commercial_message_requires_unsubscribe_url(self) -> None:
        policy = self.active_policy()
        with self.assertRaises(ValueError):
            MODULE.compose_plain_text_message(
                policy,
                body="Commercial message",
                subject="Offer",
                recipients=["recipient@example.com"],
                signer_name="John Kaminski",
                signer_title="Authorized Representative",
                message_class="commercial",
                timestamp=self.now,
            )

    def test_control_headers_reject_injection(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.build_control_headers(control_id="WWCX-ABC\r\nBcc: victim@example.com")

    def test_audit_record_hashes_subject_and_excludes_body(self) -> None:
        policy = self.active_policy()
        result = MODULE.compose_plain_text_message(
            policy,
            body="Highly sensitive body text",
            subject="Sensitive subject",
            recipients=["recipient@example.com"],
            signer_name="John Kaminski",
            signer_title="Authorized Representative",
            timestamp=self.now,
        )
        serialized = json.dumps(result["audit_record"])
        self.assertNotIn("Highly sensitive body text", serialized)
        self.assertNotIn("Sensitive subject", serialized)
        self.assertEqual(result["audit_record"]["recipient_count"], 1)


if __name__ == "__main__":
    unittest.main()
