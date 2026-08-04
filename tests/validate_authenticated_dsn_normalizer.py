#!/usr/bin/env python3
"""Validate authenticated DSN normalization and suppression integration."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/messaging/normalize_authenticated_dsn.py"
SCHEMA = ROOT / "schemas/messaging/authenticated-dsn-evidence.schema.json"
DOC = ROOT / "docs/messaging-operations/authenticated-dsn-normalization-20260804.md"
SPEC = importlib.util.spec_from_file_location("dsn_normalizer", TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load DSN normalizer")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))
import outbound_mail_delivery_events as delivery_events


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def dsn_message() -> bytes:
    return b"""From: MAILER-DAEMON@example.net\r
To: bounce-review@ww.cx\r
Date: Tue, 04 Aug 2026 03:20:00 +0000\r
Subject: Delivery Status Notification\r
MIME-Version: 1.0\r
Content-Type: multipart/report; report-type=delivery-status; boundary=dsn-boundary\r
\r
--dsn-boundary\r
Content-Type: text/plain; charset=utf-8\r
\r
Delivery status details are available in the machine-readable part.\r
--dsn-boundary\r
Content-Type: message/delivery-status\r
\r
Reporting-MTA: dns; mx.example.net\r
Arrival-Date: Tue, 04 Aug 2026 03:19:00 +0000\r
\r
Final-Recipient: rfc822; Failed.Person@Example.com\r
Action: failed\r
Status: 5.1.1\r
Diagnostic-Code: smtp; 550 5.1.1 confidential raw diagnostic\r
Last-Attempt-Date: Tue, 04 Aug 2026 03:19:10 +0000\r
\r
Final-Recipient: rfc822; delayed.person@example.com\r
Action: delayed\r
Status: 4.4.1\r
Diagnostic-Code: smtp; 451 temporary routing failure\r
Last-Attempt-Date: Tue, 04 Aug 2026 03:19:20 +0000\r
\r
Final-Recipient: rfc822; delivered.person@example.com\r
Action: delivered\r
Status: 2.0.0\r
Last-Attempt-Date: Tue, 04 Aug 2026 03:19:30 +0000\r
\r
--dsn-boundary--\r
"""


def manifest(raw: bytes) -> dict:
    return {
        "contract": MODULE.MANIFEST_CONTRACT,
        "captured_at": "2026-08-04T03:21:00+00:00",
        "source_authentication": "authenticated_mailbox_dsn",
        "source_verified": True,
        "mailbox_identity_sha256": "a" * 64,
        "evidence_sha256": hashlib.sha256(raw).hexdigest(),
        "provider_profile": "smtp_submission",
        "provider_message_id_sha256": "b" * 64,
        "control_id": "WWCX-DSN-TEST-0001",
        "raw_message_restricted": True,
        "credentials_included": False,
        "message_content_committed": False,
    }


for path in (TOOL, SCHEMA, DOC):
    check(path.is_file(), f"missing {path}")
    check(path.stat().st_size > 500, f"undersized {path}")

schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
check(schema["$schema"] == "https://json-schema.org/draft/2020-12/schema", "schema draft mismatch")
check(schema["properties"]["contract"]["const"] == MODULE.MANIFEST_CONTRACT, "manifest contract mismatch")
check(schema["additionalProperties"] is False, "manifest schema permits extra fields")
check(schema["properties"]["source_verified"]["const"] is True, "manifest permits unverified source")
check(schema["properties"]["credentials_included"]["const"] is False, "manifest permits credentials")

raw = dsn_message()
report = MODULE.normalize(raw, manifest(raw))
serialized = json.dumps(report, sort_keys=True)
check(report["contract"] == MODULE.OUTPUT_CONTRACT, "output contract mismatch")
check(report["event_count"] == 3, "multi-recipient DSN event count mismatch")
check(report["source_verified"] is True, "normalized source is not verified")
check(report["raw_recipient_stored"] is False, "normalized output reports raw recipients")
check(report["raw_diagnostic_stored"] is False, "normalized output reports raw diagnostics")
check(report["message_content_stored"] is False, "normalized output reports message content")
check(report["credentials_inspected"] is False, "normalizer inspected credentials")
check(report["network_access_performed"] is False, "normalizer performed network access")
check(report["mailbox_access_performed"] is False, "normalizer accessed a mailbox")
check(report["message_sent"] is False, "normalizer reports message activity")

by_type = {item["event_type"]: item for item in report["events"]}
check(set(by_type) == {"permanent_bounce", "transient_bounce", "delivered"}, "event classification mismatch")
permanent = by_type["permanent_bounce"]
transient = by_type["transient_bounce"]
delivered = by_type["delivered"]
check(permanent["diagnostic_class"] == "mailbox_unavailable", "permanent diagnostic class mismatch")
check(permanent["retryable"] is False, "permanent bounce became retryable")
check(permanent["occurred_at"] == "2026-08-04T03:19:10+00:00", "permanent timestamp mismatch")
check(transient["diagnostic_class"] == "domain_unavailable", "transient diagnostic class mismatch")
check(transient["retryable"] is True, "transient bounce is not retryable")
check(delivered["diagnostic_class"] == "none", "delivered diagnostic class mismatch")
check(delivered["retryable"] is False, "delivered event became retryable")
for item in report["events"]:
    delivery_events.validate_event(item)
    check(item["source_evidence_sha256"] == hashlib.sha256(raw).hexdigest(), "source evidence hash mismatch")
    check(item["provider_message_id_sha256"] == "b" * 64, "provider message ID hash mismatch")
    check(item["control_id"] == "WWCX-DSN-TEST-0001", "control ID mismatch")
    check(item["event_id"].startswith("dsn:"), "deterministic DSN event ID prefix mismatch")

for forbidden in (
    "failed.person@example.com",
    "delayed.person@example.com",
    "delivered.person@example.com",
    "confidential raw diagnostic",
    "temporary routing failure",
    "MAILER-DAEMON",
    "bounce-review@ww.cx",
):
    check(forbidden.casefold() not in serialized.casefold(), f"normalized output leaked {forbidden}")

repeat = MODULE.normalize(raw, manifest(raw))
check(
    [item["event_id"] for item in repeat["events"]]
    == [item["event_id"] for item in report["events"]],
    "DSN event IDs are not deterministic",
)

invalid_manifests: list[tuple[str, dict]] = []
hash_mismatch = manifest(raw)
hash_mismatch["evidence_sha256"] = "f" * 64
invalid_manifests.append(("hash mismatch", hash_mismatch))
unverified = manifest(raw)
unverified["source_verified"] = False
invalid_manifests.append(("unverified source", unverified))
credentialed = manifest(raw)
credentialed["credentials_included"] = True
invalid_manifests.append(("credential-bearing evidence", credentialed))
unrestricted = manifest(raw)
unrestricted["raw_message_restricted"] = False
invalid_manifests.append(("unrestricted raw message", unrestricted))
for label, candidate in invalid_manifests:
    failed_closed = False
    try:
        MODULE.normalize(raw, candidate)
    except MODULE.DsnNormalizationError:
        failed_closed = True
    check(failed_closed, f"invalid {label} did not fail closed")

wrong_type = raw.replace(
    b"multipart/report; report-type=delivery-status",
    b"multipart/mixed",
    1,
)
wrong_manifest = manifest(wrong_type)
failed_closed = False
try:
    MODULE.normalize(wrong_type, wrong_manifest)
except MODULE.DsnNormalizationError:
    failed_closed = True
check(failed_closed, "non-DSN MIME message did not fail closed")

unsupported = raw.replace(b"Action: delayed", b"Action: failed", 1).replace(
    b"Status: 4.4.1", b"Status: 2.0.0", 1
)
unsupported_manifest = manifest(unsupported)
failed_closed = False
try:
    MODULE.normalize(unsupported, unsupported_manifest)
except MODULE.DsnNormalizationError:
    failed_closed = True
check(failed_closed, "unsupported action/status combination did not fail closed")

with tempfile.TemporaryDirectory() as temporary:
    folder = pathlib.Path(temporary)
    database = folder / "delivery.sqlite3"
    for item in report["events"]:
        delivery_events.apply_event(database, item)
    permanent_state = delivery_events.recipient_state(database, permanent["recipient_sha256"])
    transient_state = delivery_events.recipient_state(database, transient["recipient_sha256"])
    delivered_state = delivery_events.recipient_state(database, delivered["recipient_sha256"])
    check(permanent_state["suppression_active"] is True, "permanent DSN did not suppress")
    check(permanent_state["suppression_reason"] == "permanent_bounce", "permanent suppression reason mismatch")
    check(transient_state["suppression_active"] is False, "transient DSN suppressed recipient")
    check(transient_state["transient_failure_count"] == 1, "transient DSN count mismatch")
    check(delivered_state["suppression_active"] is False, "delivered DSN suppressed recipient")

    dsn_path = folder / "dsn.eml"
    manifest_path = folder / "manifest.json"
    output_path = folder / "normalized.json"
    dsn_path.write_bytes(raw)
    manifest_path.write_text(json.dumps(manifest(raw)), encoding="utf-8")
    process = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--dsn",
            str(dsn_path),
            "--manifest",
            str(manifest_path),
            "--output",
            str(output_path),
            "--pretty",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    check(process.returncode == 0, f"DSN CLI failed: {process.stderr}")
    cli_report = json.loads(output_path.read_text(encoding="utf-8"))
    check(cli_report["event_count"] == 3, "DSN CLI event count mismatch")
    check("example.com" not in output_path.read_text(encoding="utf-8").casefold(), "DSN CLI leaked a recipient domain")

    refused_output = ROOT / "var" / "forbidden-dsn-output.json"
    refused = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--dsn",
            str(dsn_path),
            "--manifest",
            str(manifest_path),
            "--output",
            str(refused_output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    check(refused.returncode == 2, "DSN CLI accepted output inside Git worktree")
    check("refusing normalized DSN output" in refused.stderr, "DSN worktree refusal reason changed")
    check(not refused_output.exists(), "DSN CLI wrote forbidden worktree output")

source = TOOL.read_text(encoding="utf-8")
for required in (
    "parses only the machine-readable message/delivery-status part",
    "authenticated_mailbox_dsn",
    "raw DSN SHA-256 does not match the manifest",
    "Final-Recipient",
    "unsupported DSN action/status combination",
    "raw_recipient_stored",
    "raw_diagnostic_stored",
    "network_access_performed",
    "message_sent",
    "refusing normalized DSN output inside the Git working tree",
):
    check(required in source, f"normalizer missing safety marker: {required}")
for prohibited in (
    "requests.",
    "urllib.request",
    "imaplib",
    "poplib",
    "smtplib",
    "subprocess.",
    "apply_event(",
):
    check(prohibited not in source, f"normalizer contains prohibited operation: {prohibited}")

print("Authenticated DSN normalization validation passed")
print("Permanent, transient, delivered, forged, malformed, and multi-recipient cases verified")
print("Recipient addresses and raw diagnostics are reduced to hashes and bounded classes")
print("Normalized permanent bounces create suppression; transient and delivered events do not")
print("No credential, mailbox access, network request, message content retention, or message traffic occurs")
