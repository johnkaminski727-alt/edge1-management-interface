#!/usr/bin/env python3
"""Sanitized, reviewable Mail Room quarantine metadata contract.

This module records bounded security metadata only. It does not store message
bodies or attachment bytes, does not delete mail, and does not release quarantine.
Release eligibility is advisory to an authorized operator workflow and AI can never
satisfy or replace the required human/security gates.
"""

from __future__ import annotations

import re
from typing import Any


CONTRACT = "wwcx.mail-quarantine.v1"
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
CONTROL_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{5,127}$")
ALLOWED_DISPOSITIONS = {"quarantine"}
ALLOWED_ROUTE_DECISIONS = {
    "security_quarantine",
    "policy_quarantine",
    "manual_review",
}


class QuarantineError(ValueError):
    """Raised for malformed quarantine metadata or release facts."""


def _text(value: Any, label: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QuarantineError(f"{label} must be non-empty text")
    normalized = value.strip()
    if "\r" in normalized or "\n" in normalized or len(normalized) > maximum:
        raise QuarantineError(f"{label} is invalid")
    return normalized


def _hex64(value: Any, label: str) -> str:
    normalized = _text(value, label, 64).casefold()
    if not HEX64_RE.fullmatch(normalized):
        raise QuarantineError(f"{label} must be SHA-256 hex")
    return normalized


def build_record(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise QuarantineError("quarantine data must be an object")
    expected = {
        "quarantine_id",
        "correspondence_id",
        "message_sha256",
        "original_recipient_sha256",
        "created_at",
        "route_decision",
        "reason_codes",
        "security_signals",
        "scan_evidence",
        "provenance",
    }
    if set(data) != expected:
        raise QuarantineError("quarantine data keys are invalid")

    quarantine_id = _text(data["quarantine_id"], "quarantine_id", 128)
    if not CONTROL_ID_RE.fullmatch(quarantine_id):
        raise QuarantineError("quarantine_id is invalid")
    correspondence_id = _text(data["correspondence_id"], "correspondence_id", 128)
    if not CONTROL_ID_RE.fullmatch(correspondence_id):
        raise QuarantineError("correspondence_id is invalid")
    created_at = _text(data["created_at"], "created_at", 64)
    if "T" not in created_at:
        raise QuarantineError("created_at must be ISO-8601-like")
    route_decision = _text(data["route_decision"], "route_decision", 64)
    if route_decision not in ALLOWED_ROUTE_DECISIONS:
        raise QuarantineError("route_decision is unsupported")

    reason_codes = data["reason_codes"]
    if not isinstance(reason_codes, list) or not reason_codes or len(reason_codes) > 64:
        raise QuarantineError("reason_codes must be a bounded non-empty list")
    normalized_reasons = [_text(item, "reason code", 128) for item in reason_codes]
    if len(set(normalized_reasons)) != len(normalized_reasons):
        raise QuarantineError("reason_codes must be unique")

    security_signals = data["security_signals"]
    if not isinstance(security_signals, list) or len(security_signals) > 128:
        raise QuarantineError("security_signals must be a bounded list")
    normalized_signals = [_text(item, "security signal", 192) for item in security_signals]

    scan_evidence = data["scan_evidence"]
    if not isinstance(scan_evidence, list) or len(scan_evidence) > 32:
        raise QuarantineError("scan_evidence must be a bounded list")
    normalized_scans: list[dict[str, str]] = []
    for item in scan_evidence:
        if not isinstance(item, dict) or set(item) != {
            "engine", "engine_version", "ruleset_version", "state"
        }:
            raise QuarantineError("scan evidence keys are invalid")
        normalized_scans.append(
            {
                "engine": _text(item["engine"], "scan engine", 128),
                "engine_version": _text(item["engine_version"], "engine version", 128),
                "ruleset_version": _text(item["ruleset_version"], "ruleset version", 128),
                "state": _text(item["state"], "scan state", 64).casefold(),
            }
        )

    provenance = data["provenance"]
    if not isinstance(provenance, dict) or set(provenance) != {
        "source", "source_event_sha256", "decision_contract"
    }:
        raise QuarantineError("provenance keys are invalid")

    return {
        "contract": CONTRACT,
        "quarantine_id": quarantine_id,
        "correspondence_id": correspondence_id,
        "message_sha256": _hex64(data["message_sha256"], "message_sha256"),
        "original_recipient_sha256": _hex64(
            data["original_recipient_sha256"], "original_recipient_sha256"
        ),
        "created_at": created_at,
        "disposition": "quarantine",
        "route_decision": route_decision,
        "reason_codes": normalized_reasons,
        "security_signals": normalized_signals,
        "scan_evidence": normalized_scans,
        "provenance": {
            "source": _text(provenance["source"], "provenance.source", 128),
            "source_event_sha256": _hex64(
                provenance["source_event_sha256"], "provenance.source_event_sha256"
            ),
            "decision_contract": _text(
                provenance["decision_contract"], "provenance.decision_contract", 128
            ),
        },
        "message_body_stored": False,
        "attachment_bytes_stored": False,
        "active_content_executed": False,
        "automatic_release_allowed": False,
        "ai_release_allowed": False,
    }


def evaluate_release(facts: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(facts, dict):
        raise QuarantineError("release facts must be an object")
    expected = {
        "operator_approved",
        "security_rescan_clean",
        "destination_validated",
        "policy_authorized",
        "ai_requested_release",
    }
    if set(facts) != expected or any(not isinstance(facts[key], bool) for key in expected):
        raise QuarantineError("release facts must contain only boolean authoritative gates")

    reasons: list[str] = []
    if facts["ai_requested_release"]:
        reasons.append("ai_release_request_has_no_authority")
    if not facts["operator_approved"]:
        reasons.append("operator_approval_required")
    if not facts["security_rescan_clean"]:
        reasons.append("clean_security_rescan_required")
    if not facts["destination_validated"]:
        reasons.append("validated_destination_required")
    if not facts["policy_authorized"]:
        reasons.append("policy_authorization_required")

    return {
        "contract": CONTRACT,
        "eligible_for_operator_release": not reasons,
        "automatic_release_attempted": False,
        "ai_has_release_authority": False,
        "block_reasons": reasons,
    }
