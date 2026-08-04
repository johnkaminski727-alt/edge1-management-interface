#!/usr/bin/env python3
"""Validate the outbound-mail delivery-event and suppression foundation."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "server/outbound_mail_delivery_events.py"
CLI = ROOT / "tools/messaging/outbound_mail_delivery_event_cli.py"
SCHEMA = ROOT / "schemas/messaging/outbound-mail-delivery-event.schema.json"
DOC = ROOT / "docs/messaging-operations/outbound-mail-delivery-event-foundation-20260804.md"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


for path in (SERVER, CLI, SCHEMA, DOC):
    check(path.is_file(), f"missing {path}")
    check(path.stat().st_size > 500, f"undersized {path}")

schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
check(schema["$schema"] == "https://json-schema.org/draft/2020-12/schema", "schema draft mismatch")
check(schema["properties"]["contract"]["const"] == "wwcx.outbound-mail-delivery-event.v1", "schema contract mismatch")
check(schema["additionalProperties"] is False, "schema must reject extra fields")
check(schema["properties"]["raw_recipient_stored"]["const"] is False, "schema permits raw recipients")
check(schema["properties"]["raw_payload_stored"]["const"] is False, "schema permits raw payloads")
check(schema["properties"]["message_content_stored"]["const"] is False, "schema permits message content")

text = SERVER.read_text(encoding="utf-8")
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
    check(required in text, f"delivery-event core missing {required}")
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
    check(prohibited not in text, f"delivery-event core contains prohibited operation {prohibited}")

cli_text = CLI.read_text(encoding="utf-8")
check("Synthetic events require an explicit test-only flag" in cli_text, "CLI synthetic-event warning missing")
check("--allow-synthetic" in cli_text, "CLI synthetic gate missing")
check("provider credentials" in cli_text, "CLI no-credential boundary missing")

compile_result = subprocess.run(
    [sys.executable, "-m", "py_compile", str(SERVER), str(CLI)],
    cwd=ROOT,
    check=False,
)
check(compile_result.returncode == 0, "delivery-event Python did not compile")

unit_result = subprocess.run(
    [sys.executable, "-m", "unittest", "tests.test_outbound_mail_delivery_events"],
    cwd=ROOT,
    check=False,
)
check(unit_result.returncode == 0, "delivery-event unit tests failed")

print("Outbound mail delivery-event foundation validation passed")
print("Verified minimized events, idempotence, conflict detection, and durable suppression state")
print("Permanent bounces, complaints, and unsubscribes suppress; transient failures remain retryable")
print("Suppressions are never cleared automatically and no network listener or message traffic exists")
