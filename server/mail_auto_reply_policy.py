#!/usr/bin/env python3
"""Fail-closed Mail Room automatic-reply eligibility policy.

This module only evaluates eligibility. It does not compose, queue, transmit, or
submit mail and contains no provider/network client code.
"""

from __future__ import annotations

from typing import Any


CONTRACT = "wwcx.mail-auto-reply-policy.v1"
DEFAULT_MODE = "prepare_only"
REQUIRED_GATE_NAMES = {
    "security_clean",
    "phishing_bec_risk_acceptable",
    "sender_identity_confident",
    "thread_identity_confident",
    "outbound_sender_live_authorized",
    "footer_profile_resolved",
    "message_class_allowlisted",
    "idempotency_passed",
    "final_outbound_scan_clean",
    "domain_policy_allows",
    "identity_policy_allows",
    "workflow_policy_allows",
    "human_approval_not_required",
}


class AutoReplyPolicyError(ValueError):
    """Raised for invalid auto-reply policy or decision inputs."""


def validate_policy(policy: dict[str, Any]) -> None:
    if not isinstance(policy, dict):
        raise AutoReplyPolicyError("auto-reply policy must be an object")
    expected = {
        "contract",
        "enabled",
        "automatic_transmission_authorized",
        "default_mode",
        "allowlisted_message_classes",
        "blocked_message_classes",
        "required_gates",
    }
    if set(policy) != expected:
        raise AutoReplyPolicyError("auto-reply policy keys are invalid")
    if policy["contract"] != CONTRACT:
        raise AutoReplyPolicyError("unsupported auto-reply policy contract")
    if not isinstance(policy["enabled"], bool):
        raise AutoReplyPolicyError("enabled must be boolean")
    if not isinstance(policy["automatic_transmission_authorized"], bool):
        raise AutoReplyPolicyError("automatic_transmission_authorized must be boolean")
    if policy["default_mode"] != DEFAULT_MODE:
        raise AutoReplyPolicyError("default_mode must remain prepare_only")
    for name in ("allowlisted_message_classes", "blocked_message_classes", "required_gates"):
        value = policy[name]
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise AutoReplyPolicyError(f"{name} must be a list of non-empty strings")
        if len(set(value)) != len(value):
            raise AutoReplyPolicyError(f"{name} must not contain duplicates")
    if set(policy["required_gates"]) != REQUIRED_GATE_NAMES:
        raise AutoReplyPolicyError("required_gates must include every authoritative safety gate")
    if set(policy["allowlisted_message_classes"]) & set(policy["blocked_message_classes"]):
        raise AutoReplyPolicyError("a message class cannot be both allowlisted and blocked")
    if policy["automatic_transmission_authorized"] and not policy["enabled"]:
        raise AutoReplyPolicyError("automatic transmission authorization requires enabled=true")


def evaluate(policy: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    validate_policy(policy)
    if not isinstance(facts, dict):
        raise AutoReplyPolicyError("auto-reply facts must be an object")

    message_class = str(facts.get("message_class", "")).strip()
    blocked_classes = set(policy["blocked_message_classes"])
    allowlisted_classes = set(policy["allowlisted_message_classes"])

    gate_values = {
        "security_clean": facts.get("security_disposition") == "clean",
        "phishing_bec_risk_acceptable": facts.get("phishing_bec_risk") in {"none", "low"},
        "sender_identity_confident": facts.get("sender_identity_confident") is True,
        "thread_identity_confident": facts.get("thread_identity_confident") is True,
        "outbound_sender_live_authorized": facts.get("outbound_sender_live_authorized") is True,
        "footer_profile_resolved": facts.get("footer_profile_resolved") is True,
        "message_class_allowlisted": bool(message_class and message_class in allowlisted_classes),
        "idempotency_passed": facts.get("idempotency_passed") is True,
        "final_outbound_scan_clean": facts.get("final_outbound_scan") == "clean",
        "domain_policy_allows": facts.get("domain_policy_allows") is True,
        "identity_policy_allows": facts.get("identity_policy_allows") is True,
        "workflow_policy_allows": facts.get("workflow_policy_allows") is True,
        "human_approval_not_required": facts.get("human_approval_required") is False,
    }

    reasons: list[str] = []
    if not policy["enabled"]:
        reasons.append("auto_reply_policy_disabled")
    if not policy["automatic_transmission_authorized"]:
        reasons.append("automatic_transmission_not_authorized")
    if not message_class:
        reasons.append("message_class_missing")
    if message_class in blocked_classes:
        reasons.append("high_risk_message_class_blocked")
    for gate_name in policy["required_gates"]:
        if not gate_values[gate_name]:
            reasons.append(f"gate_failed:{gate_name}")

    eligible = not reasons
    return {
        "contract": CONTRACT,
        "mode": "auto_send" if eligible else DEFAULT_MODE,
        "eligible": eligible,
        "message_class": message_class or None,
        "gate_results": gate_values,
        "block_reasons": reasons,
        "automatic_transmission_attempted": False,
    }
