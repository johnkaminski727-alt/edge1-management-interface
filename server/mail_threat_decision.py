#!/usr/bin/env python3
"""Provider-neutral, fail-closed Mail Room threat decision runtime.

Consumes normalized security facts only. It does not parse hostile MIME, execute
attachments, call AI, contact reputation services, release quarantine, or deliver
mail. AI-derived risk may escalate a disposition but can never weaken a hard
security result.
"""

from __future__ import annotations

from typing import Any


CONTRACT = "wwcx.mail-threat-decision.v1"
SCAN_STATES = {
    "clean",
    "infected",
    "suspicious",
    "unscannable",
    "scan_error",
    "not_scanned",
}
HARD_QUARANTINE_SCAN_STATES = SCAN_STATES - {"clean"}
RISK_LEVELS = {"none", "low", "medium", "high", "critical", "unknown"}
AUTH_STATES = {"pass", "fail", "softfail", "neutral", "none", "unknown"}


class ThreatDecisionError(ValueError):
    """Raised for malformed or unsafe normalized threat facts."""


def _bounded_text(value: Any, label: str, maximum: int = 128) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ThreatDecisionError(f"{label} must be non-empty text")
    normalized = value.strip()
    if "\r" in normalized or "\n" in normalized or len(normalized) > maximum:
        raise ThreatDecisionError(f"{label} is invalid")
    return normalized


def _risk(value: Any, label: str) -> str:
    normalized = _bounded_text(value, label).casefold()
    if normalized not in RISK_LEVELS:
        raise ThreatDecisionError(f"{label} is unsupported")
    return normalized


def _scan_results(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ThreatDecisionError("scan_results must be a list")
    results: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ThreatDecisionError("scan result must be an object")
        expected = {"engine", "engine_version", "ruleset_version", "state", "reason_codes"}
        if set(item) != expected:
            raise ThreatDecisionError("scan result keys are invalid")
        state = _bounded_text(item["state"], "scan state").casefold()
        if state not in SCAN_STATES:
            raise ThreatDecisionError("scan state is unsupported")
        reason_codes = item["reason_codes"]
        if not isinstance(reason_codes, list) or len(reason_codes) > 64:
            raise ThreatDecisionError("scan reason_codes are invalid")
        normalized_reasons = [
            _bounded_text(reason, "scan reason code") for reason in reason_codes
        ]
        if len(set(normalized_reasons)) != len(normalized_reasons):
            raise ThreatDecisionError("scan reason_codes contain duplicates")
        results.append(
            {
                "engine": _bounded_text(item["engine"], "scan engine"),
                "engine_version": _bounded_text(item["engine_version"], "engine version"),
                "ruleset_version": _bounded_text(item["ruleset_version"], "ruleset version"),
                "state": state,
                "reason_codes": normalized_reasons,
            }
        )
    return results


def evaluate(policy: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(policy, dict) or policy.get("contract") != "wwcx.mail-threat-policy.v1":
        raise ThreatDecisionError("unsupported threat policy")
    if not isinstance(facts, dict):
        raise ThreatDecisionError("threat facts must be an object")

    scan_results = _scan_results(facts.get("scan_results", []))
    phishing_risk = _risk(facts.get("phishing_risk", "unknown"), "phishing_risk")
    bec_risk = _risk(facts.get("bec_risk", "unknown"), "bec_risk")
    spam_risk = _risk(facts.get("spam_risk", "unknown"), "spam_risk")
    ai_risk = _risk(facts.get("ai_risk", "unknown"), "ai_risk")
    auth = facts.get("authentication")
    if not isinstance(auth, dict) or set(auth) != {"spf", "dkim", "dmarc", "arc"}:
        raise ThreatDecisionError("authentication must contain SPF, DKIM, DMARC, and ARC")
    normalized_auth: dict[str, str] = {}
    for name, state_value in auth.items():
        state = _bounded_text(state_value, f"authentication.{name}").casefold()
        if state not in AUTH_STATES:
            raise ThreatDecisionError(f"authentication.{name} is unsupported")
        normalized_auth[name] = state

    reasons: list[str] = []
    hard_security_block = False
    required_scan = bool(policy.get("malware", {}).get("required"))
    fail_closed = bool(policy.get("malware", {}).get("fail_closed"))

    if required_scan and not scan_results:
        hard_security_block = True
        reasons.append("required_scan_missing")
    for result in scan_results:
        if result["state"] in HARD_QUARANTINE_SCAN_STATES:
            hard_security_block = True
            reasons.append(f"scan:{result['engine']}:{result['state']}")
        reasons.extend(f"scan_reason:{code}" for code in result["reason_codes"])

    if fail_closed and any(value in {"unknown", "none"} for value in normalized_auth.values()):
        reasons.append("authentication_incomplete")
    if normalized_auth["dmarc"] == "fail":
        hard_security_block = True
        reasons.append("dmarc_fail")

    for label, risk in (("phishing", phishing_risk), ("bec", bec_risk)):
        if risk in {"high", "critical"}:
            hard_security_block = True
            reasons.append(f"{label}_{risk}")
    if ai_risk in {"high", "critical"}:
        reasons.append(f"ai_risk_{ai_risk}")

    if hard_security_block:
        disposition = "quarantine"
    elif ai_risk in {"high", "critical"}:
        disposition = "quarantine"
    elif spam_risk in {"high", "critical"}:
        disposition = "spam_folder"
    elif required_scan and any(item["state"] != "clean" for item in scan_results):
        disposition = "quarantine"
    else:
        disposition = "deliver"

    return {
        "contract": CONTRACT,
        "disposition": disposition,
        "hard_security_block": hard_security_block,
        "scan_complete": bool(scan_results) and all(item["state"] == "clean" for item in scan_results),
        "authentication": normalized_auth,
        "phishing_risk": phishing_risk,
        "bec_risk": bec_risk,
        "spam_risk": spam_risk,
        "ai_risk": ai_risk,
        "reason_codes": list(dict.fromkeys(reasons)),
        "ai_may_reduce_hard_security_risk": False,
        "ai_may_release_quarantine": False,
    }
