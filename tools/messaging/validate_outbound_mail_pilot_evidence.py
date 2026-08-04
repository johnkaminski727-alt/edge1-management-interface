#!/usr/bin/env python3
"""Validate one bounded outbound-mail pilot evidence record.

The validator is offline and read-only. It validates metadata and cryptographic
hashes only; it never reads provider credentials, message bodies, recipient
addresses, complete headers, or external evidence files. Validation of an
executed record is evidence review, not authorization to send another message.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any


CONTRACT = "wwcx.outbound-mail-controlled-pilot-evidence.v1"
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
PILOT_RE = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{7,127}$")
EMAIL_RE = re.compile(r"^[^@\s]+@([^@\s]+)$")
FORBIDDEN_KEYS = {
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "authorization",
    "authorization_header",
    "cookie",
    "private_key",
    "message_body",
    "body",
    "raw_message",
    "raw_headers",
    "complete_headers",
    "recipient_address",
    "smtp_password",
}


class PilotEvidenceError(RuntimeError):
    """Raised when pilot evidence is malformed, unsafe, or incomplete."""


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotEvidenceError(f"unable to read pilot evidence: {exc}") from exc
    if not isinstance(value, dict):
        raise PilotEvidenceError("pilot evidence must be a JSON object")
    return value


def require_exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PilotEvidenceError(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        raise PilotEvidenceError(
            f"{label} keys invalid; missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )
    return value


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise PilotEvidenceError(f"{label} must be boolean")
    return value


def require_text(value: Any, label: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise PilotEvidenceError(f"{label} must be non-empty text")
    return value.strip()


def require_hash(value: Any, label: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not HEX64_RE.fullmatch(value):
        raise PilotEvidenceError(f"{label} must be a lowercase SHA-256 digest")
    return value


def require_nullable_timestamp(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or "T" not in value or not (value.endswith("Z") or "+" in value[10:]):
        raise PilotEvidenceError(f"{label} must be an ISO-8601 timestamp or null")
    return value


def walk_forbidden(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if normalized in FORBIDDEN_KEYS:
                raise PilotEvidenceError(f"forbidden inline field at {path}.{key}")
            walk_forbidden(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            walk_forbidden(item, f"{path}[{index}]")


def all_true(value: dict[str, Any], keys: tuple[str, ...], label: str) -> None:
    false_keys = [key for key in keys if value.get(key) is not True]
    if false_keys:
        raise PilotEvidenceError(f"{label} requires true values for {false_keys}")


def all_false(value: dict[str, Any], keys: tuple[str, ...], label: str) -> None:
    true_keys = [key for key in keys if value.get(key) is not False]
    if true_keys:
        raise PilotEvidenceError(f"{label} requires false values for {true_keys}")


def validate(value: dict[str, Any]) -> dict[str, Any]:
    walk_forbidden(value)
    top = require_exact_keys(
        value,
        {
            "contract",
            "captured_at",
            "execution_status",
            "pilot_id",
            "scope",
            "authorizations",
            "preflight",
            "submission",
            "receipt",
            "authentication",
            "audit_linkage",
            "rollback",
            "safety",
            "evidence_files",
            "failure_reasons",
        },
        "pilot evidence",
    )
    if top["contract"] != CONTRACT:
        raise PilotEvidenceError("unsupported pilot evidence contract")
    status = top["execution_status"]
    if status not in {"not_executed", "executed_pass", "executed_fail", "rolled_back"}:
        raise PilotEvidenceError("unsupported execution status")
    require_nullable_timestamp(top["captured_at"], "captured_at")
    if not isinstance(top["pilot_id"], str) or not PILOT_RE.fullmatch(top["pilot_id"]):
        raise PilotEvidenceError("pilot_id is invalid")

    scope = require_exact_keys(
        top["scope"],
        {
            "provider_profile",
            "provider_family",
            "sender_address",
            "sender_domain",
            "recipient_address_sha256",
            "recipient_domain",
            "recipient_owned_by_wwcx",
            "message_class",
            "subject_sha256",
            "body_sha256",
            "message_count",
            "recipient_count",
        },
        "scope",
    )
    for key in ("provider_profile", "provider_family", "sender_address", "sender_domain", "recipient_domain"):
        require_text(scope[key], f"scope.{key}", nullable=True)
    require_hash(scope["recipient_address_sha256"], "scope.recipient_address_sha256", nullable=True)
    require_hash(scope["subject_sha256"], "scope.subject_sha256", nullable=True)
    require_hash(scope["body_sha256"], "scope.body_sha256", nullable=True)
    require_bool(scope["recipient_owned_by_wwcx"], "scope.recipient_owned_by_wwcx")
    if scope["message_class"] not in {"test_business_correspondence", "not_selected"}:
        raise PilotEvidenceError("scope.message_class is invalid")
    for key in ("message_count", "recipient_count"):
        if not isinstance(scope[key], int) or scope[key] not in {0, 1}:
            raise PilotEvidenceError(f"scope.{key} must be 0 or 1")
    if scope["sender_address"] is not None:
        match = EMAIL_RE.fullmatch(scope["sender_address"])
        if not match:
            raise PilotEvidenceError("scope.sender_address is invalid")
        if scope["sender_domain"] != match.group(1).casefold():
            raise PilotEvidenceError("scope.sender_domain does not match sender_address")

    authorizations = require_exact_keys(
        top["authorizations"],
        {
            "provider_terms_reviewed",
            "provider_credential_installation_authorized",
            "sender_activation_authorized",
            "runtime_cutover_authorized",
            "exact_recipient_authorized",
            "exact_message_authorized",
            "production_message_traffic_authorized",
            "authorization_reference",
        },
        "authorizations",
    )
    authorization_flags = (
        "provider_terms_reviewed",
        "provider_credential_installation_authorized",
        "sender_activation_authorized",
        "runtime_cutover_authorized",
        "exact_recipient_authorized",
        "exact_message_authorized",
        "production_message_traffic_authorized",
    )
    for key in authorization_flags:
        require_bool(authorizations[key], f"authorizations.{key}")
    require_text(authorizations["authorization_reference"], "authorizations.authorization_reference", nullable=True)

    preflight = require_exact_keys(
        top["preflight"],
        {
            "repository_commit",
            "clean_main",
            "gateway_enabled",
            "deployment_authorized",
            "external_delivery_authorized",
            "send_endpoint_enabled",
            "policy_enabled",
            "smtp_cutover_authorized",
            "provider_selected",
            "provider_ready",
            "sender_allowlisted",
            "canonical_sender_provider_object_verified",
            "spf_path_verified",
            "dkim_dns_verified",
            "dmarc_record_published",
            "return_path_defined",
            "bounce_ingestion_ready",
            "complaint_suppression_ready",
            "rollback_verified",
        },
        "preflight",
    )
    if preflight["repository_commit"] is not None and (
        not isinstance(preflight["repository_commit"], str)
        or not SHA40_RE.fullmatch(preflight["repository_commit"])
    ):
        raise PilotEvidenceError("preflight.repository_commit is invalid")
    preflight_flags = tuple(key for key in preflight if key != "repository_commit")
    for key in preflight_flags:
        require_bool(preflight[key], f"preflight.{key}")

    submission = require_exact_keys(
        top["submission"],
        {
            "attempted",
            "accepted_by_provider",
            "provider_message_id_sha256",
            "gateway_http_status",
            "provider_response_class",
            "submitted_at",
        },
        "submission",
    )
    require_bool(submission["attempted"], "submission.attempted")
    require_bool(submission["accepted_by_provider"], "submission.accepted_by_provider")
    require_hash(submission["provider_message_id_sha256"], "submission.provider_message_id_sha256", nullable=True)
    if submission["gateway_http_status"] is not None and (
        not isinstance(submission["gateway_http_status"], int)
        or not 100 <= submission["gateway_http_status"] <= 599
    ):
        raise PilotEvidenceError("submission.gateway_http_status is invalid")
    if submission["provider_response_class"] not in {
        "not_attempted",
        "accepted",
        "temporary_failure",
        "permanent_failure",
        "unknown",
    }:
        raise PilotEvidenceError("submission.provider_response_class is invalid")
    require_nullable_timestamp(submission["submitted_at"], "submission.submitted_at")

    receipt = require_exact_keys(
        top["receipt"],
        {
            "received",
            "received_at",
            "recipient_address_sha256",
            "message_id_sha256",
            "subject_hash_matches",
            "body_hash_matches",
            "controlled_footer_present",
            "control_headers_present",
            "complete_headers_evidence_sha256",
        },
        "receipt",
    )
    receipt_flags = (
        "received",
        "subject_hash_matches",
        "body_hash_matches",
        "controlled_footer_present",
        "control_headers_present",
    )
    for key in receipt_flags:
        require_bool(receipt[key], f"receipt.{key}")
    require_nullable_timestamp(receipt["received_at"], "receipt.received_at")
    for key in (
        "recipient_address_sha256",
        "message_id_sha256",
        "complete_headers_evidence_sha256",
    ):
        require_hash(receipt[key], f"receipt.{key}", nullable=True)

    authentication = require_exact_keys(
        top["authentication"],
        {
            "dkim_result",
            "dkim_selector",
            "dkim_signing_domain",
            "dkim_from_alignment",
            "spf_result",
            "spf_envelope_domain",
            "spf_from_alignment",
            "dmarc_result",
            "dmarc_policy",
            "dmarc_aligned",
        },
        "authentication",
    )
    if authentication["dkim_result"] not in {"not_tested", "pass", "fail", "neutral", "temperror", "permerror", "none"}:
        raise PilotEvidenceError("authentication.dkim_result is invalid")
    if authentication["spf_result"] not in {"not_tested", "pass", "fail", "softfail", "neutral", "temperror", "permerror", "none"}:
        raise PilotEvidenceError("authentication.spf_result is invalid")
    if authentication["dmarc_result"] not in {"not_tested", "pass", "fail", "none"}:
        raise PilotEvidenceError("authentication.dmarc_result is invalid")
    if authentication["dmarc_policy"] not in {"not_observed", "none", "quarantine", "reject"}:
        raise PilotEvidenceError("authentication.dmarc_policy is invalid")
    for key in ("dkim_selector", "dkim_signing_domain", "spf_envelope_domain"):
        require_text(authentication[key], f"authentication.{key}", nullable=True)
    for key in ("dkim_from_alignment", "spf_from_alignment", "dmarc_aligned"):
        require_bool(authentication[key], f"authentication.{key}")

    audit = require_exact_keys(
        top["audit_linkage"],
        {
            "control_id",
            "gateway_event_id",
            "gateway_audit_record_sha256",
            "provider_message_id_matches",
            "receipt_message_id_matches",
            "recipient_hash_matches",
        },
        "audit_linkage",
    )
    require_text(audit["control_id"], "audit_linkage.control_id", nullable=True)
    require_text(audit["gateway_event_id"], "audit_linkage.gateway_event_id", nullable=True)
    require_hash(audit["gateway_audit_record_sha256"], "audit_linkage.gateway_audit_record_sha256", nullable=True)
    audit_flags = ("provider_message_id_matches", "receipt_message_id_matches", "recipient_hash_matches")
    for key in audit_flags:
        require_bool(audit[key], f"audit_linkage.{key}")

    rollback = require_exact_keys(
        top["rollback"],
        {
            "plan_reference",
            "available",
            "executed",
            "reason",
            "post_rollback_safe_disabled",
            "evidence_sha256",
        },
        "rollback",
    )
    require_text(rollback["plan_reference"], "rollback.plan_reference", nullable=True)
    require_bool(rollback["available"], "rollback.available")
    require_bool(rollback["executed"], "rollback.executed")
    require_text(rollback["reason"], "rollback.reason", nullable=True)
    require_bool(rollback["post_rollback_safe_disabled"], "rollback.post_rollback_safe_disabled")
    require_hash(rollback["evidence_sha256"], "rollback.evidence_sha256", nullable=True)

    safety = require_exact_keys(
        top["safety"],
        {
            "single_message_only",
            "single_recipient_only",
            "bulk_traffic_enabled",
            "commercial_traffic_enabled",
            "customer_traffic_enabled",
            "regulatory_traffic_enabled",
            "emergency_traffic_enabled",
            "provider_credentials_inspected_by_validator",
            "message_body_stored_inline",
            "recipient_address_stored_inline",
            "complete_headers_stored_inline",
            "message_sent",
        },
        "safety",
    )
    for key in safety:
        require_bool(safety[key], f"safety.{key}")
    all_true(safety, ("single_message_only", "single_recipient_only"), "safety")
    all_false(
        safety,
        (
            "bulk_traffic_enabled",
            "commercial_traffic_enabled",
            "customer_traffic_enabled",
            "regulatory_traffic_enabled",
            "emergency_traffic_enabled",
            "provider_credentials_inspected_by_validator",
            "message_body_stored_inline",
            "recipient_address_stored_inline",
            "complete_headers_stored_inline",
        ),
        "safety",
    )

    evidence_files = top["evidence_files"]
    if not isinstance(evidence_files, list) or len(evidence_files) > 50:
        raise PilotEvidenceError("evidence_files must be a list with at most 50 entries")
    roles: set[str] = set()
    for index, item in enumerate(evidence_files):
        evidence = require_exact_keys(
            item,
            {"role", "restricted_path", "sha256", "contains_message_content", "contains_credentials"},
            f"evidence_files[{index}]",
        )
        role = require_text(evidence["role"], f"evidence_files[{index}].role")
        if role in roles:
            raise PilotEvidenceError("evidence file roles must be unique")
        roles.add(role)
        path = require_text(evidence["restricted_path"], f"evidence_files[{index}].restricted_path")
        if path.startswith("http://") or path.startswith("https://"):
            raise PilotEvidenceError("evidence paths must be restricted filesystem references, not URLs")
        require_hash(evidence["sha256"], f"evidence_files[{index}].sha256")
        require_bool(evidence["contains_message_content"], f"evidence_files[{index}].contains_message_content")
        if evidence["contains_credentials"] is not False:
            raise PilotEvidenceError("pilot evidence must not include credential-bearing files")

    failure_reasons = top["failure_reasons"]
    if not isinstance(failure_reasons, list) or len(failure_reasons) > 100:
        raise PilotEvidenceError("failure_reasons must be a list with at most 100 entries")
    if any(not isinstance(item, str) or not item.strip() or len(item) > 512 for item in failure_reasons):
        raise PilotEvidenceError("failure_reasons contains an invalid item")

    if status == "not_executed":
        if top["captured_at"] is not None:
            raise PilotEvidenceError("not_executed evidence must not set captured_at")
        all_false(authorizations, authorization_flags, "not_executed authorizations")
        if authorizations["authorization_reference"] is not None:
            raise PilotEvidenceError("not_executed evidence must not set authorization_reference")
        if scope["message_count"] != 0 or scope["recipient_count"] != 0:
            raise PilotEvidenceError("not_executed evidence must have zero message and recipient counts")
        if any(scope[key] is not None for key in ("provider_profile", "provider_family", "sender_address", "sender_domain", "recipient_address_sha256", "recipient_domain", "subject_sha256", "body_sha256")):
            raise PilotEvidenceError("not_executed evidence must not select provider, sender, recipient, or content")
        if scope["recipient_owned_by_wwcx"] or scope["message_class"] != "not_selected":
            raise PilotEvidenceError("not_executed scope is inconsistent")
        if preflight["repository_commit"] is not None or any(preflight[key] for key in preflight_flags):
            raise PilotEvidenceError("not_executed evidence must not report completed preflight gates")
        if submission["attempted"] or submission["accepted_by_provider"] or submission["provider_response_class"] != "not_attempted":
            raise PilotEvidenceError("not_executed submission state is inconsistent")
        if receipt["received"] or any(receipt[key] for key in receipt_flags[1:]):
            raise PilotEvidenceError("not_executed receipt state is inconsistent")
        if authentication["dkim_result"] != "not_tested" or authentication["spf_result"] != "not_tested" or authentication["dmarc_result"] != "not_tested":
            raise PilotEvidenceError("not_executed authentication state is inconsistent")
        if any(audit[key] for key in audit_flags):
            raise PilotEvidenceError("not_executed audit linkage is inconsistent")
        if rollback["available"] or rollback["executed"] or rollback["post_rollback_safe_disabled"]:
            raise PilotEvidenceError("not_executed rollback state is inconsistent")
        if safety["message_sent"]:
            raise PilotEvidenceError("not_executed evidence cannot report a sent message")
        if evidence_files or failure_reasons:
            raise PilotEvidenceError("not_executed example must not contain evidence files or failures")

    if status == "executed_pass":
        require_nullable_timestamp(top["captured_at"], "captured_at")
        if top["captured_at"] is None:
            raise PilotEvidenceError("executed_pass requires captured_at")
        all_true(authorizations, authorization_flags, "executed_pass authorizations")
        if authorizations["authorization_reference"] is None:
            raise PilotEvidenceError("executed_pass requires an authorization reference")
        if scope["message_count"] != 1 or scope["recipient_count"] != 1:
            raise PilotEvidenceError("executed_pass must contain exactly one message and one recipient")
        if scope["provider_profile"] != "smtp_submission" or not scope["provider_family"]:
            raise PilotEvidenceError("executed_pass requires the approved SMTP provider")
        if scope["sender_address"] is None or scope["recipient_address_sha256"] is None:
            raise PilotEvidenceError("executed_pass requires sender and recipient-hash scope")
        if not scope["recipient_owned_by_wwcx"] or scope["message_class"] != "test_business_correspondence":
            raise PilotEvidenceError("executed_pass requires an owned test recipient and test message class")
        if scope["subject_sha256"] is None or scope["body_sha256"] is None:
            raise PilotEvidenceError("executed_pass requires subject and body hashes")
        if preflight["repository_commit"] is None:
            raise PilotEvidenceError("executed_pass requires the deployed commit")
        all_true(preflight, preflight_flags, "executed_pass preflight")
        if not submission["attempted"] or not submission["accepted_by_provider"]:
            raise PilotEvidenceError("executed_pass requires provider acceptance")
        if submission["provider_response_class"] != "accepted" or submission["provider_message_id_sha256"] is None:
            raise PilotEvidenceError("executed_pass provider evidence is incomplete")
        if submission["gateway_http_status"] not in {200, 202} or submission["submitted_at"] is None:
            raise PilotEvidenceError("executed_pass gateway submission evidence is invalid")
        all_true(receipt, receipt_flags, "executed_pass receipt")
        if receipt["received_at"] is None or receipt["message_id_sha256"] is None or receipt["complete_headers_evidence_sha256"] is None:
            raise PilotEvidenceError("executed_pass receipt evidence is incomplete")
        if receipt["recipient_address_sha256"] != scope["recipient_address_sha256"]:
            raise PilotEvidenceError("executed_pass recipient hashes do not match")
        if authentication["dkim_result"] != "pass" or authentication["dkim_selector"] != "default":
            raise PilotEvidenceError("executed_pass requires DKIM pass with selector default")
        if authentication["dkim_signing_domain"] != scope["sender_domain"] or not authentication["dkim_from_alignment"]:
            raise PilotEvidenceError("executed_pass requires aligned DKIM signing domain")
        if authentication["spf_result"] != "pass" or not authentication["spf_from_alignment"]:
            raise PilotEvidenceError("executed_pass requires aligned SPF pass")
        if authentication["dmarc_result"] != "pass" or authentication["dmarc_policy"] == "not_observed" or not authentication["dmarc_aligned"]:
            raise PilotEvidenceError("executed_pass requires an observed aligned DMARC pass")
        if audit["control_id"] is None or audit["gateway_event_id"] is None or audit["gateway_audit_record_sha256"] is None:
            raise PilotEvidenceError("executed_pass audit identifiers are incomplete")
        all_true(audit, audit_flags, "executed_pass audit linkage")
        if not rollback["available"] or rollback["plan_reference"] is None:
            raise PilotEvidenceError("executed_pass requires an available rollback plan")
        if rollback["executed"] or rollback["post_rollback_safe_disabled"]:
            raise PilotEvidenceError("executed_pass must not claim rollback execution")
        if not safety["message_sent"]:
            raise PilotEvidenceError("executed_pass must acknowledge one sent message")
        required_roles = {"preflight", "gateway_audit", "provider_submission", "received_headers", "receipt", "rollback_plan"}
        if not required_roles.issubset(roles):
            raise PilotEvidenceError(f"executed_pass evidence files missing roles {sorted(required_roles - roles)}")
        if failure_reasons:
            raise PilotEvidenceError("executed_pass cannot contain failure reasons")

    if status in {"executed_fail", "rolled_back"}:
        if top["captured_at"] is None or not submission["attempted"]:
            raise PilotEvidenceError(f"{status} requires a timestamp and attempted submission")
        if not authorizations["exact_message_authorized"] or not authorizations["production_message_traffic_authorized"]:
            raise PilotEvidenceError(f"{status} must preserve exact message authorization evidence")
        if not failure_reasons:
            raise PilotEvidenceError(f"{status} requires failure reasons")
        if status == "rolled_back":
            if not rollback["available"] or not rollback["executed"] or not rollback["post_rollback_safe_disabled"]:
                raise PilotEvidenceError("rolled_back requires completed safe rollback evidence")
            if rollback["evidence_sha256"] is None:
                raise PilotEvidenceError("rolled_back requires rollback evidence digest")
        if safety["message_sent"] != submission["attempted"]:
            raise PilotEvidenceError(f"{status} message_sent must reflect the attempted production message")

    return {
        "contract": CONTRACT,
        "pilot_id": top["pilot_id"],
        "execution_status": status,
        "valid": True,
        "message_count": scope["message_count"],
        "recipient_count": scope["recipient_count"],
        "message_sent": safety["message_sent"],
        "provider_credentials_inspected": False,
        "message_content_inspected": False,
        "evidence_file_count": len(evidence_files),
        "failure_count": len(failure_reasons),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=pathlib.Path)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--require-pass", action="store_true")
    parser.add_argument("--require-not-executed", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = validate(load_json(args.evidence))
    except PilotEvidenceError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.require_pass and result["execution_status"] != "executed_pass":
        print("pilot evidence is valid but does not record an executed pass", file=sys.stderr)
        return 3
    if args.require_not_executed and result["execution_status"] != "not_executed":
        print("pilot evidence is valid but is not the unexecuted template", file=sys.stderr)
        return 4
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
