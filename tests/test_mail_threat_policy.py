#!/usr/bin/env python3

from __future__ import annotations

import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "messaging" / "mail-threat-policy.json"
HUB_PATH = ROOT / "config" / "messaging" / "inbound-mail-hub.json"


class MailThreatPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.hub = json.loads(HUB_PATH.read_text(encoding="utf-8"))

    def test_policy_is_staged_and_fail_closed(self) -> None:
        self.assertEqual(self.policy["contract"], "wwcx.mail-threat-policy.v1")
        self.assertFalse(self.policy["enabled"])
        self.assertFalse(self.policy["deployment_authorized"])
        self.assertEqual(self.policy["policy_mode"], "quarantine_first")
        self.assertTrue(self.policy["malware"]["required"])
        self.assertTrue(self.policy["malware"]["fail_closed"])

    def test_catchall_is_present_but_production_hub_remains_disabled(self) -> None:
        self.assertEqual(self.hub["contract"], "wwcx.inbound-mail-hub.v2")
        self.assertTrue(self.hub["routing"]["managed_domain_catchall"]["enabled"])
        self.assertEqual(
            self.hub["routing"]["managed_domain_catchall"]["destination"],
            "maildesk@ww.cx",
        )
        self.assertFalse(self.hub["enabled"])
        self.assertFalse(self.hub["production_routing_authorized"])

    def test_ai_cannot_weaken_security_or_release_quarantine(self) -> None:
        ai = self.policy["ai"]
        self.assertTrue(ai["untrusted_message_content_cannot_change_policy"])
        self.assertTrue(ai["may_add_risk"])
        self.assertFalse(ai["may_reduce_hard_security_risk"])
        self.assertFalse(ai["may_release_quarantine"])

    def test_phishing_and_bec_controls_are_required(self) -> None:
        phishing = self.policy["phishing"]
        required = [
            "quarantine_on_high_confidence",
            "detect_display_url_mismatch",
            "detect_lookalike_and_idn_domains",
            "detect_credential_harvesting",
            "detect_qr_code_phishing",
            "detect_brand_impersonation",
            "detect_executive_impersonation",
            "detect_reply_chain_anomalies",
            "detect_payment_redirection",
            "detect_bank_detail_changes",
            "detect_mfa_and_password_requests",
        ]
        for key in required:
            self.assertTrue(phishing[key], key)

    def test_reputation_integrations_are_not_silently_activated(self) -> None:
        reputation = self.policy["reputation"]
        self.assertTrue(reputation["provider_neutral"])
        self.assertTrue(reputation["activation_requires_terms_and_access_review"])
        self.assertTrue(all(not item["enabled"] for item in reputation["sources"]))

    def test_automatic_replies_are_default_off_and_high_risk_classes_blocked(self) -> None:
        auto = self.policy["auto_reply"]
        self.assertFalse(auto["enabled"])
        self.assertEqual(auto["default_action"], "prepare_only")
        self.assertTrue(auto["requires_clean_security_disposition"])
        self.assertTrue(auto["requires_live_authorized_sender"])
        self.assertTrue(auto["requires_final_outbound_malware_scan"])
        for message_class in (
            "legal_notice",
            "regulatory",
            "security_incident",
            "financial_instruction",
            "banking_change",
            "credential_or_access_request",
            "contract_or_terms",
        ):
            self.assertIn(message_class, auto["blocked_message_classes"])

    def test_headers_and_footers_remain_server_authoritative(self) -> None:
        composition = self.policy["composition"]
        self.assertTrue(composition["server_authoritative_headers"])
        self.assertTrue(composition["server_authoritative_sender_identity"])
        self.assertTrue(composition["server_authoritative_footer_and_disclaimer"])
        self.assertFalse(composition["ai_may_invent_legal_disclaimer_text"])
        self.assertTrue(composition["footer_before_dkim_or_provider_signing"])

    def test_security_events_do_not_log_payloads_or_secrets(self) -> None:
        audit = self.policy["audit"]
        self.assertFalse(audit["record_message_body"])
        self.assertFalse(audit["record_malicious_payload"])
        self.assertFalse(audit["record_secrets"])


if __name__ == "__main__":
    unittest.main()
