#!/usr/bin/env python3
"""Validate the controlled outbound-mail pilot evidence contract."""

from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/messaging/validate_outbound_mail_pilot_evidence.py"
SCHEMA_PATH = ROOT / "schemas/messaging/outbound-mail-pilot-evidence.schema.json"
EXAMPLE_PATH = ROOT / "examples/messaging/outbound-mail-pilot-evidence.not-executed.example.json"
SPEC = importlib.util.spec_from_file_location("pilot_evidence", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load pilot evidence validator")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def valid_pass() -> dict:
    digest = "a" * 64
    return {
        "contract": MODULE.CONTRACT,
        "captured_at": "2026-08-04T01:00:00Z",
        "execution_status": "executed_pass",
        "pilot_id": "WWCX-MAIL-PILOT-0001",
        "scope": {
            "provider_profile": "smtp_submission",
            "provider_family": "namecheap_private_email",
            "sender_address": "john@ww.cx",
            "sender_domain": "ww.cx",
            "recipient_address_sha256": "b" * 64,
            "recipient_domain": "ww.cx",
            "recipient_owned_by_wwcx": True,
            "message_class": "test_business_correspondence",
            "subject_sha256": "c" * 64,
            "body_sha256": "d" * 64,
            "message_count": 1,
            "recipient_count": 1,
        },
        "authorizations": {
            "provider_terms_reviewed": True,
            "provider_credential_installation_authorized": True,
            "sender_activation_authorized": True,
            "runtime_cutover_authorized": True,
            "exact_recipient_authorized": True,
            "exact_message_authorized": True,
            "production_message_traffic_authorized": True,
            "authorization_reference": "approved-change/WWCX-MAIL-PILOT-0001",
        },
        "preflight": {
            "repository_commit": "e" * 40,
            "clean_main": True,
            "gateway_enabled": True,
            "deployment_authorized": True,
            "external_delivery_authorized": True,
            "send_endpoint_enabled": True,
            "policy_enabled": True,
            "smtp_cutover_authorized": True,
            "provider_selected": True,
            "provider_ready": True,
            "sender_allowlisted": True,
            "canonical_sender_provider_object_verified": True,
            "spf_path_verified": True,
            "dkim_dns_verified": True,
            "dmarc_record_published": True,
            "return_path_defined": True,
            "bounce_ingestion_ready": True,
            "complaint_suppression_ready": True,
            "rollback_verified": True,
        },
        "submission": {
            "attempted": True,
            "accepted_by_provider": True,
            "provider_message_id_sha256": "f" * 64,
            "gateway_http_status": 202,
            "provider_response_class": "accepted",
            "submitted_at": "2026-08-04T01:00:01Z",
        },
        "receipt": {
            "received": True,
            "received_at": "2026-08-04T01:00:05Z",
            "recipient_address_sha256": "b" * 64,
            "message_id_sha256": "1" * 64,
            "subject_hash_matches": True,
            "body_hash_matches": True,
            "controlled_footer_present": True,
            "control_headers_present": True,
            "complete_headers_evidence_sha256": "2" * 64,
        },
        "authentication": {
            "dkim_result": "pass",
            "dkim_selector": "default",
            "dkim_signing_domain": "ww.cx",
            "dkim_from_alignment": True,
            "spf_result": "pass",
            "spf_envelope_domain": "ww.cx",
            "spf_from_alignment": True,
            "dmarc_result": "pass",
            "dmarc_policy": "none",
            "dmarc_aligned": True,
        },
        "audit_linkage": {
            "control_id": "WWCX-20260804-PILOT-0001",
            "gateway_event_id": "event-0001",
            "gateway_audit_record_sha256": "3" * 64,
            "provider_message_id_matches": True,
            "receipt_message_id_matches": True,
            "recipient_hash_matches": True,
        },
        "rollback": {
            "plan_reference": "rollback/WWCX-MAIL-PILOT-0001",
            "available": True,
            "executed": False,
            "reason": None,
            "post_rollback_safe_disabled": False,
            "evidence_sha256": None,
        },
        "safety": {
            "single_message_only": True,
            "single_recipient_only": True,
            "bulk_traffic_enabled": False,
            "commercial_traffic_enabled": False,
            "customer_traffic_enabled": False,
            "regulatory_traffic_enabled": False,
            "emergency_traffic_enabled": False,
            "provider_credentials_inspected_by_validator": False,
            "message_body_stored_inline": False,
            "recipient_address_stored_inline": False,
            "complete_headers_stored_inline": False,
            "message_sent": True,
        },
        "evidence_files": [
            {
                "role": role,
                "restricted_path": f"/restricted/pilot/{role}.json",
                "sha256": digest,
                "contains_message_content": role in {"received_headers", "receipt"},
                "contains_credentials": False,
            }
            for role in (
                "preflight",
                "gateway_audit",
                "provider_submission",
                "received_headers",
                "receipt",
                "rollback_plan",
            )
        ],
        "failure_reasons": [],
    }


schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
check(schema["$schema"] == "https://json-schema.org/draft/2020-12/schema", "schema draft mismatch")
check(schema["properties"]["contract"]["const"] == MODULE.CONTRACT, "schema contract mismatch")
check(schema["additionalProperties"] is False, "schema must reject extra top-level properties")

unexecuted = MODULE.validate(example)
check(unexecuted["execution_status"] == "not_executed", "unexecuted example status mismatch")
check(unexecuted["message_count"] == 0 and unexecuted["recipient_count"] == 0, "unexecuted counts changed")
check(unexecuted["message_sent"] is False, "unexecuted example reports message activity")
check(unexecuted["provider_credentials_inspected"] is False, "validator inspected credentials")
check(unexecuted["message_content_inspected"] is False, "validator inspected message content")

passed = MODULE.validate(valid_pass())
check(passed["execution_status"] == "executed_pass", "valid pass was rejected")
check(passed["message_count"] == 1 and passed["recipient_count"] == 1, "valid pass scope mismatch")
check(passed["message_sent"] is True, "valid pass does not record the one message")

invalid_cases: list[tuple[str, dict]] = []
missing_auth = valid_pass()
missing_auth["authorizations"]["production_message_traffic_authorized"] = False
invalid_cases.append(("production authorization", missing_auth))

missing_dmarc = valid_pass()
missing_dmarc["preflight"]["dmarc_record_published"] = False
invalid_cases.append(("DMARC preflight", missing_dmarc))

bad_dkim = valid_pass()
bad_dkim["authentication"]["dkim_selector"] = "privateemail"
invalid_cases.append(("DKIM selector", bad_dkim))

unaligned_spf = valid_pass()
unaligned_spf["authentication"]["spf_from_alignment"] = False
invalid_cases.append(("SPF alignment", unaligned_spf))

missing_headers = valid_pass()
missing_headers["receipt"]["complete_headers_evidence_sha256"] = None
invalid_cases.append(("complete headers evidence", missing_headers))

raw_body = valid_pass()
raw_body["message_body"] = "forbidden content"
invalid_cases.append(("raw message body", raw_body))

raw_recipient = valid_pass()
raw_recipient["scope"]["recipient_address"] = "test@ww.cx"
invalid_cases.append(("raw recipient address", raw_recipient))

credential_file = valid_pass()
credential_file["evidence_files"][0]["contains_credentials"] = True
invalid_cases.append(("credential-bearing evidence file", credential_file))

unowned_recipient = valid_pass()
unowned_recipient["scope"]["recipient_owned_by_wwcx"] = False
invalid_cases.append(("unowned recipient", unowned_recipient))

for label, candidate in invalid_cases:
    failed_closed = False
    try:
        MODULE.validate(candidate)
    except MODULE.PilotEvidenceError:
        failed_closed = True
    check(failed_closed, f"invalid {label} did not fail closed")

rolled_back = valid_pass()
rolled_back["execution_status"] = "rolled_back"
rolled_back["submission"]["accepted_by_provider"] = False
rolled_back["submission"]["provider_response_class"] = "temporary_failure"
rolled_back["receipt"]["received"] = False
rolled_back["receipt"]["received_at"] = None
rolled_back["receipt"]["subject_hash_matches"] = False
rolled_back["receipt"]["body_hash_matches"] = False
rolled_back["receipt"]["controlled_footer_present"] = False
rolled_back["receipt"]["control_headers_present"] = False
rolled_back["authentication"]["dkim_result"] = "not_tested"
rolled_back["authentication"]["dkim_selector"] = None
rolled_back["authentication"]["dkim_signing_domain"] = None
rolled_back["authentication"]["dkim_from_alignment"] = False
rolled_back["authentication"]["spf_result"] = "not_tested"
rolled_back["authentication"]["spf_envelope_domain"] = None
rolled_back["authentication"]["spf_from_alignment"] = False
rolled_back["authentication"]["dmarc_result"] = "not_tested"
rolled_back["authentication"]["dmarc_aligned"] = False
rolled_back["rollback"]["executed"] = True
rolled_back["rollback"]["reason"] = "Provider submission failed during bounded pilot."
rolled_back["rollback"]["post_rollback_safe_disabled"] = True
rolled_back["rollback"]["evidence_sha256"] = "4" * 64
rolled_back["failure_reasons"] = ["Provider submission returned a temporary failure."]
rolled = MODULE.validate(rolled_back)
check(rolled["execution_status"] == "rolled_back", "valid rollback record was rejected")

with tempfile.TemporaryDirectory() as temporary:
    path = pathlib.Path(temporary) / "pilot.json"
    path.write_text(json.dumps(example), encoding="utf-8")
    process = subprocess.run(
        [sys.executable, str(MODULE_PATH), str(path), "--require-not-executed", "--pretty"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    check(process.returncode == 0, f"unexecuted CLI validation failed: {process.stderr}")
    output = json.loads(process.stdout)
    check(output["execution_status"] == "not_executed", "CLI status mismatch")

print("Controlled outbound-mail pilot evidence validation passed")
print("One-message authorization, preflight, authentication, receipt, audit, and rollback gates verified")
print("Raw bodies, recipient addresses, credentials, and inline complete headers fail closed")
print("The committed example remains unexecuted and no message is authorized or sent")
