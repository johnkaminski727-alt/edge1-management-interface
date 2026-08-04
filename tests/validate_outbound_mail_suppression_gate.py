#!/usr/bin/env python3
"""Validate the fail-closed outbound-mail suppression send gate."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import outbound_mail_delivery_events as delivery_events
import outbound_mail_gateway as gateway
import outbound_mail_suppression_gate as gate


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def synthetic_event(event_id: str, recipient_sha256: str, event_type: str, diagnostic: str) -> dict:
    return {
        "contract": delivery_events.CONTRACT,
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": "2026-08-04T02:00:00Z",
        "provider_profile": "smtp_submission",
        "provider_message_id_sha256": "a" * 64,
        "control_id": "WWCX-SUPPRESSION-TEST-0001",
        "recipient_sha256": recipient_sha256,
        "source_evidence_sha256": "b" * 64,
        "source_authentication": "synthetic_test",
        "source_verified": True,
        "diagnostic_class": diagnostic,
        "retryable": event_type == "transient_bounce",
        "raw_recipient_stored": False,
        "raw_payload_stored": False,
        "message_content_stored": False,
    }


gateway_config = json.loads(
    (ROOT / "config/messaging/outbound-mail-gateway.json").read_text(encoding="utf-8")
)
gateway.validate_gateway_config(gateway_config)
payload = {
    "to": ["Test.Recipient@Example.com"],
    "subject": "Suppression gate synthetic validation",
    "body": "Synthetic body used only to exercise normalization.",
    "message_class": "business_correspondence",
}
recipient_hash = gate.recipient_sha256("test.recipient@example.com")
check(recipient_hash == gate.recipient_sha256(" Test.Recipient@Example.com "), "recipient hashing is not normalized")
check(len(recipient_hash) == 64 and "@" not in recipient_hash, "recipient hash is invalid")

with tempfile.TemporaryDirectory() as temporary:
    root = pathlib.Path(temporary)
    missing = root / "missing.sqlite3"
    failed_closed = False
    try:
        gate.suppression_preflight(missing, ["test.recipient@example.com"])
    except gate.SuppressionStateUnavailableError as exc:
        failed_closed = "suppression state is unavailable" in str(exc)
    check(failed_closed, "missing required suppression database did not fail closed")

    optional = gate.suppression_preflight(
        missing,
        ["test.recipient@example.com"],
        required=False,
    )
    check(optional["checked"] is False, "optional missing database was reported checked")
    check(optional["database_present"] is False, "optional missing database was reported present")
    check(optional["recipient_hashes"] == [recipient_hash], "optional preflight hash mismatch")
    check("@" not in json.dumps(optional), "optional preflight exposed recipient address")

    database = root / "delivery.sqlite3"
    delivery_events.apply_event(
        database,
        synthetic_event(
            "event-suppressed-0001",
            recipient_hash,
            "complaint",
            "spam_complaint",
        ),
        allow_synthetic=True,
    )
    called = False

    def fake_send(*args, **kwargs):
        nonlocal_called[0] = True
        return {"status": "accepted"}

    nonlocal_called = [False]
    failed_closed = False
    try:
        gate.guarded_identity_send(
            fake_send,
            gateway_config,
            {},
            {},
            payload,
            confirmation=True,
            audit_path=root / "audit.jsonl",
            suppression_database=database,
        )
    except gate.SuppressedRecipientError as exc:
        failed_closed = (
            len(exc.suppressed) == 1
            and exc.suppressed[0]["recipient_sha256"] == recipient_hash
            and "complaint" in str(exc)
            and "example.com" not in str(exc)
        )
    check(failed_closed, "active suppression did not fail closed")
    check(nonlocal_called[0] is False, "underlying send callable ran for suppressed recipient")

    allowed_database = root / "allowed.sqlite3"
    delivery_events.apply_event(
        allowed_database,
        synthetic_event(
            "event-allowed-0001",
            "c" * 64,
            "provider_accepted",
            "none",
        ),
        allow_synthetic=True,
    )
    call_count = [0]

    def allowed_send(config, policy, identities, request_payload, *, confirmation, audit_path):
        call_count[0] += 1
        check(config is gateway_config, "guard changed gateway configuration")
        check(request_payload is payload, "guard changed request payload")
        check(confirmation is True, "guard changed send confirmation")
        check(pathlib.Path(audit_path) == root / "audit.jsonl", "guard changed audit path")
        return {"status": "accepted", "provider_message_id": "synthetic-id"}

    result = gate.guarded_identity_send(
        allowed_send,
        gateway_config,
        {},
        {},
        payload,
        confirmation=True,
        audit_path=root / "audit.jsonl",
        suppression_database=allowed_database,
    )
    check(call_count[0] == 1, "allowed send callable did not run exactly once")
    check(result["status"] == "accepted", "allowed send result changed")
    check(result["suppression_preflight"] == {
        "checked": True,
        "recipient_count": 1,
        "suppressed_recipient_count": 0,
    }, "allowed suppression preflight result mismatch")
    check("test.recipient@example.com" not in json.dumps(result), "guard result exposed recipient address")

module_text = (SERVER / "outbound_mail_suppression_gate.py").read_text(encoding="utf-8")
for required in (
    "Fail-closed pre-send suppression checks",
    "SuppressionStateUnavailableError",
    "SuppressedRecipientError",
    "suppression_preflight",
    "guarded_identity_send",
    "send_callable",
):
    check(required in module_text, f"suppression gate missing {required}")
for prohibited in (
    "smtplib",
    "requests.",
    "urllib.request",
    "clear_suppression",
    "delete_suppression",
    "unsuppress",
):
    check(prohibited not in module_text, f"suppression gate contains prohibited operation {prohibited}")

print("Outbound mail suppression send-gate validation passed")
print("Missing state and active hashed-recipient suppression fail closed before the send callable")
print("Allowed recipients invoke the underlying send callable exactly once")
print("No credential, raw recipient, suppression mutation, provider connection, or message is performed")
