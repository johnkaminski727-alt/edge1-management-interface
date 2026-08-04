#!/usr/bin/env python3
"""Validate the outbound-mail delivery-event and suppression foundation."""

from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import outbound_mail_delivery_events as module

CLI = ROOT / "tools/messaging/outbound_mail_delivery_event_cli.py"
SCHEMA = ROOT / "schemas/messaging/outbound-mail-delivery-event.schema.json"
DOC = ROOT / "docs/messaging-operations/outbound-mail-delivery-event-foundation-20260804.md"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def event(
    event_id: str,
    event_type: str,
    diagnostic_class: str,
    *,
    recipient: str = "a" * 64,
) -> dict:
    return {
        "contract": module.CONTRACT,
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": "2026-08-04T01:00:00Z",
        "provider_profile": "smtp_submission",
        "provider_message_id_sha256": "b" * 64,
        "control_id": "WWCX-PILOT-CONTROL-0001",
        "recipient_sha256": recipient,
        "source_evidence_sha256": "c" * 64,
        "source_authentication": "synthetic_test",
        "source_verified": True,
        "diagnostic_class": diagnostic_class,
        "retryable": event_type == "transient_bounce",
        "raw_recipient_stored": False,
        "raw_payload_stored": False,
        "message_content_stored": False,
    }


for path in (pathlib.Path(module.__file__), CLI, SCHEMA, DOC):
    check(path.is_file(), f"missing {path}")
    check(path.stat().st_size > 500, f"undersized {path}")

schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
check(schema["$schema"] == "https://json-schema.org/draft/2020-12/schema", "schema draft mismatch")
check(schema["properties"]["contract"]["const"] == module.CONTRACT, "schema contract mismatch")
check(schema["additionalProperties"] is False, "schema must reject extra fields")
check(schema["properties"]["raw_recipient_stored"]["const"] is False, "schema permits raw recipients")
check(schema["properties"]["raw_payload_stored"]["const"] is False, "schema permits raw payloads")
check(schema["properties"]["message_content_stored"]["const"] is False, "schema permits message content")

server_text = pathlib.Path(module.__file__).read_text(encoding="utf-8")
for required in (
    "Permanent bounces, complaints and unsubscribe",
    "SUPPRESSIVE_TYPES",
    "source_verified",
    "raw_recipient_stored",
    "raw_payload_stored",
    "message_content_stored",
    "delivery event ID was reused with different evidence",
    "suppression_active",
    "transient_failure_count",
    "suppressed_recipients",
):
    check(required in server_text, f"delivery-event core missing {required}")
for prohibited in (
    "smtplib",
    "requests.",
    "urllib.request",
    "http.server",
    "socketserver",
    "clear_suppression",
    "delete_suppression",
    "unsuppress",
):
    check(prohibited not in server_text, f"delivery-event core contains prohibited operation {prohibited}")

cli_text = CLI.read_text(encoding="utf-8")
check("Synthetic events require an explicit test-only flag" in cli_text, "CLI synthetic-event warning missing")
check("inspect provider credentials" in cli_text, "CLI no-credential boundary missing")
check("--allow-synthetic" in cli_text, "CLI synthetic gate missing")

failed_closed = False
try:
    module.validate_event(event("event-0001", "provider_accepted", "none"))
except module.DeliveryEventValidationError:
    failed_closed = True
check(failed_closed, "synthetic event did not require the test-only flag")
validated = module.validate_event(
    event("event-0001", "provider_accepted", "none"),
    allow_synthetic=True,
)
check(validated["event_type"] == "provider_accepted", "valid synthetic event failed")

raw = event("event-0002", "delivered", "none")
raw["raw_payload_stored"] = True
failed_closed = False
try:
    module.validate_event(raw, allow_synthetic=True)
except module.DeliveryEventValidationError:
    failed_closed = True
check(failed_closed, "raw payload event did not fail closed")

unverified = event("event-0003", "delivered", "none")
unverified["source_verified"] = False
failed_closed = False
try:
    module.validate_event(unverified, allow_synthetic=True)
except module.DeliveryEventValidationError:
    failed_closed = True
check(failed_closed, "unverified event source did not fail closed")

bad_retry = event("event-0004", "permanent_bounce", "mailbox_unavailable")
bad_retry["retryable"] = True
failed_closed = False
try:
    module.validate_event(bad_retry, allow_synthetic=True)
except module.DeliveryEventValidationError:
    failed_closed = True
check(failed_closed, "inconsistent retryability did not fail closed")

bad_complaint = event("event-0005", "complaint", "unknown")
failed_closed = False
try:
    module.validate_event(bad_complaint, allow_synthetic=True)
except module.DeliveryEventValidationError:
    failed_closed = True
check(failed_closed, "inconsistent complaint diagnostic did not fail closed")

with tempfile.TemporaryDirectory() as temporary:
    root = pathlib.Path(temporary)
    database = root / "delivery.sqlite3"

    transient = module.apply_event(
        database,
        event("event-1001", "transient_bounce", "rate_limited"),
        allow_synthetic=True,
    )
    check(not transient.suppression_active, "transient bounce suppressed the recipient")
    check(transient.transient_failure_count == 1, "transient failure count mismatch")
    delivered = module.apply_event(
        database,
        event("event-1002", "delivered", "none"),
        allow_synthetic=True,
    )
    check(not delivered.suppression_active, "delivery created a suppression")
    check(delivered.transient_failure_count == 0, "delivery did not reset transient failures")

    bounce = module.apply_event(
        database,
        event("event-2001", "permanent_bounce", "mailbox_unavailable"),
        allow_synthetic=True,
    )
    check(bounce.suppression_active, "permanent bounce did not suppress")
    check(bounce.suppression_reason == "permanent_bounce", "permanent bounce reason mismatch")
    delivered_after = module.apply_event(
        database,
        event("event-2002", "delivered", "none"),
        allow_synthetic=True,
    )
    check(delivered_after.suppression_active, "later delivery cleared durable suppression")
    check(delivered_after.suppression_reason == "permanent_bounce", "later delivery changed suppression reason")

    duplicate_event = event("event-3001", "complaint", "spam_complaint", recipient="d" * 64)
    first = module.apply_event(database, duplicate_event, allow_synthetic=True)
    second = module.apply_event(database, duplicate_event, allow_synthetic=True)
    check(not first.duplicate and second.duplicate, "duplicate event idempotence failed")
    check(module.recipient_state(database, "d" * 64)["event_count"] == 1, "duplicate event incremented state")
    conflicting = copy.deepcopy(duplicate_event)
    conflicting["event_type"] = "unsubscribe"
    conflicting["diagnostic_class"] = "user_unsubscribe"
    failed_closed = False
    try:
        module.apply_event(database, conflicting, allow_synthetic=True)
    except module.DeliveryEventConflictError:
        failed_closed = True
    check(failed_closed, "conflicting event ID did not fail closed")

    unsubscribe = module.apply_event(
        database,
        event("event-4001", "unsubscribe", "user_unsubscribe", recipient="e" * 64),
        allow_synthetic=True,
    )
    check(unsubscribe.suppression_active, "unsubscribe did not suppress")
    rejected = module.apply_event(
        database,
        event("event-4002", "provider_rejected", "provider_unavailable", recipient="f" * 64),
        allow_synthetic=True,
    )
    check(not rejected.suppression_active, "provider rejection incorrectly suppressed recipient")

    suppressed = module.suppressed_recipients(database, ["e" * 64, "f" * 64])
    check(len(suppressed) == 1, "suppressed recipient query mismatch")
    check(suppressed[0]["recipient_sha256"] == "e" * 64, "suppressed recipient hash mismatch")
    check("@" not in json.dumps(suppressed), "suppression state contains a raw address")

    event_path = root / "event.json"
    event_path.write_text(
        json.dumps(event("event-5001", "complaint", "spam_complaint", recipient="9" * 64)),
        encoding="utf-8",
    )
    cli_database = root / "cli-delivery.sqlite3"
    validate_cli = subprocess.run(
        [sys.executable, str(CLI), "validate", str(event_path), "--allow-synthetic"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    check(validate_cli.returncode == 0, f"CLI validate failed: {validate_cli.stderr}")
    check("@" not in validate_cli.stdout, "CLI validate output contains a raw address")
    apply_cli = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "apply",
            str(event_path),
            "--database",
            str(cli_database),
            "--allow-synthetic",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    check(apply_cli.returncode == 0, f"CLI apply failed: {apply_cli.stderr}")
    status_cli = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "status",
            "9" * 64,
            "--database",
            str(cli_database),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    check(status_cli.returncode == 0, f"CLI status failed: {status_cli.stderr}")
    cli_state = json.loads(status_cli.stdout)
    check(cli_state["suppression_active"] is True, "CLI state did not preserve complaint suppression")

print("Outbound mail delivery-event foundation validation passed")
print("Verified minimized events, idempotence, conflict detection, and durable suppression state")
print("Permanent bounces, complaints, and unsubscribes suppress; transient failures remain retryable")
print("Suppressions are never cleared automatically and no network listener or message traffic exists")
