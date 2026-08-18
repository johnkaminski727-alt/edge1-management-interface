#!/usr/bin/env python3
"""Tests for the disabled-by-default Mail Room auto-reply policy."""

from __future__ import annotations

import copy
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import mail_auto_reply_policy  # noqa: E402


POLICY_PATH = ROOT / "config" / "messaging" / "mail-auto-reply-policy.json"


def load_policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def clean_facts() -> dict:
    return {
        "message_class": "generic_contact_receipt",
        "security_disposition": "clean",
        "phishing_bec_risk": "low",
        "sender_identity_confident": True,
        "thread_identity_confident": True,
        "outbound_sender_live_authorized": True,
        "footer_profile_resolved": True,
        "idempotency_passed": True,
        "final_outbound_scan": "clean",
        "domain_policy_allows": True,
        "identity_policy_allows": True,
        "workflow_policy_allows": True,
        "human_approval_required": False,
    }


def test_committed_policy_is_prepare_only_and_disabled() -> None:
    policy = load_policy()
    mail_auto_reply_policy.validate_policy(policy)
    result = mail_auto_reply_policy.evaluate(policy, clean_facts())
    assert result["eligible"] is False
    assert result["mode"] == "prepare_only"
    assert result["automatic_transmission_attempted"] is False
    assert "auto_reply_policy_disabled" in result["block_reasons"]
    assert "automatic_transmission_not_authorized" in result["block_reasons"]
    assert "gate_failed:message_class_allowlisted" in result["block_reasons"]


def test_all_gates_are_required_even_in_hypothetical_enabled_policy() -> None:
    policy = load_policy()
    policy["enabled"] = True
    policy["automatic_transmission_authorized"] = True
    policy["allowlisted_message_classes"] = ["generic_contact_receipt"]
    facts = clean_facts()
    result = mail_auto_reply_policy.evaluate(policy, facts)
    assert result["eligible"] is True
    assert result["mode"] == "auto_send"
    assert result["automatic_transmission_attempted"] is False

    for fact_name in (
        "sender_identity_confident",
        "thread_identity_confident",
        "outbound_sender_live_authorized",
        "footer_profile_resolved",
        "idempotency_passed",
        "domain_policy_allows",
        "identity_policy_allows",
        "workflow_policy_allows",
    ):
        candidate = copy.deepcopy(facts)
        candidate[fact_name] = False
        blocked = mail_auto_reply_policy.evaluate(policy, candidate)
        assert blocked["eligible"] is False, fact_name


def test_high_risk_class_never_qualifies() -> None:
    policy = load_policy()
    policy["enabled"] = True
    policy["automatic_transmission_authorized"] = True
    policy["allowlisted_message_classes"] = ["generic_contact_receipt"]
    facts = clean_facts()
    facts["message_class"] = "payment_or_banking_change"
    result = mail_auto_reply_policy.evaluate(policy, facts)
    assert result["eligible"] is False
    assert "high_risk_message_class_blocked" in result["block_reasons"]


def test_security_and_scan_fail_closed() -> None:
    policy = load_policy()
    policy["enabled"] = True
    policy["automatic_transmission_authorized"] = True
    policy["allowlisted_message_classes"] = ["generic_contact_receipt"]

    suspicious = clean_facts()
    suspicious["security_disposition"] = "suspicious"
    assert mail_auto_reply_policy.evaluate(policy, suspicious)["eligible"] is False

    scan_error = clean_facts()
    scan_error["final_outbound_scan"] = "scan_error"
    assert mail_auto_reply_policy.evaluate(policy, scan_error)["eligible"] is False

    human_review = clean_facts()
    human_review["human_approval_required"] = True
    assert mail_auto_reply_policy.evaluate(policy, human_review)["eligible"] is False
