#!/usr/bin/env python3
"""Focused validation for fail-closed sanitized CDR and SIP-event adapters."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from telephony_sanitized_adapters import (  # noqa: E402
    SanitizedAdapterError,
    adapt_sanitized_cdr,
    adapt_sanitized_cdr_rows,
    adapt_sanitized_sip_event,
    adapt_sanitized_sip_events,
)

MODULE = ROOT / "server" / "telephony_sanitized_adapters.py"
CDR_SCHEMA = ROOT / "schemas" / "telephony" / "sanitized-cdr-record.schema.json"
SIP_SCHEMA = ROOT / "schemas" / "telephony" / "sanitized-sip-event.schema.json"
CDR_EXAMPLE = ROOT / "examples" / "telephony" / "sanitized-cdr-record.example.json"
SIP_EXAMPLE = ROOT / "examples" / "telephony" / "sanitized-sip-event.example.json"
DOC = ROOT / "docs" / "telephony" / "sanitized-event-adapters.md"

for path in (MODULE, CDR_SCHEMA, SIP_SCHEMA, CDR_EXAMPLE, SIP_EXAMPLE, DOC):
    if not path.is_file():
        raise SystemExit(f"missing sanitized adapter asset: {path.relative_to(ROOT)}")

module_source = MODULE.read_text(encoding="utf-8")
ast.parse(module_source, filename=str(MODULE))

for forbidden in (
    "import sqlite3",
    "import subprocess",
    "import socket",
    "import requests",
    "import urllib",
    "pymysql",
    "psycopg",
    "os.environ",
    "systemctl",
    "asterisk -rx",
):
    if forbidden in module_source:
        raise SystemExit(f"sanitized adapter contains prohibited access path: {forbidden}")

for required in (
    "CDR_ALLOWED_FIELDS",
    "SIP_EVENT_ALLOWED_FIELDS",
    "PROHIBITED_FIELDS",
    "adapt_sanitized_cdr",
    "adapt_sanitized_sip_event",
    "fail the entire batch",
):
    if required not in module_source:
        raise SystemExit(f"sanitized adapter missing marker: {required}")

for schema_path in (CDR_SCHEMA, SIP_SCHEMA):
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"]["const"] == "1.0"
    assert "source_record_id" in schema["required"]
    assert "observed_at" in schema["required"]

cdr_example = json.loads(CDR_EXAMPLE.read_text(encoding="utf-8"))
sip_example = json.loads(SIP_EXAMPLE.read_text(encoding="utf-8"))

cdr_event = adapt_sanitized_cdr(cdr_example)
assert cdr_event.direction == "outbound"
assert cdr_event.disposition == "answered"
assert cdr_event.sip_code == 200
assert cdr_event.carrier_id == "carrier-fixture-a"
assert cdr_event.destination_country == "CA"
assert cdr_event.duration_seconds == 42
assert cdr_event.metadata == {
    "adapter": "sanitized_cdr",
    "schema_version": "1.0",
    "source_record_id": "cdr-fixture-alpha",
    "observed_at": "2026-08-01T19:00:00Z",
}

alias_cdr = adapt_sanitized_cdr(
    {
        "schema_version": "1.0",
        "source_record_id": "cdr-alias-fixture",
        "observed_at": "2026-08-01T19:02:00Z",
        "call_direction": "incoming",
        "status": "NO ANSWER",
        "response_code": "480",
        "provider_id": "carrier-fixture-c",
        "country_code": "ca",
        "billsec": "0",
    }
)
assert alias_cdr.direction == "inbound"
assert alias_cdr.disposition == "no_answer"
assert alias_cdr.sip_code == 480
assert alias_cdr.destination_country == "CA"

sip_event = adapt_sanitized_sip_event(sip_example)
assert sip_event.direction == "inbound"
assert sip_event.disposition == "failed"
assert sip_event.sip_code == 503
assert sip_event.metadata["adapter"] == "sanitized_sip_event"
assert sip_event.metadata["event_type"] == "invite_final"

progress_event = adapt_sanitized_sip_event(
    {
        "schema_version": "1.0",
        "source_record_id": "sip-progress-fixture",
        "observed_at": "2026-08-01T19:03:00Z",
        "event_type": "invite_progress",
        "call_direction": "outgoing",
        "response_code": 183,
        "provider_id": "carrier-fixture-d",
        "country_code": "unknown",
        "duration_seconds": 0,
    }
)
assert progress_event.direction == "outbound"
assert progress_event.disposition == "progress"
assert progress_event.destination_country == "unknown"


def assert_cdr_rejected(record: dict[str, object], expected: str) -> None:
    try:
        adapt_sanitized_cdr(record)
    except SanitizedAdapterError as exc:
        if expected not in str(exc):
            raise AssertionError(f"unexpected CDR rejection: {exc}") from exc
    else:
        raise AssertionError("unsafe CDR record was accepted")


def assert_sip_rejected(record: dict[str, object], expected: str) -> None:
    try:
        adapt_sanitized_sip_event(record)
    except SanitizedAdapterError as exc:
        if expected not in str(exc):
            raise AssertionError(f"unexpected SIP rejection: {exc}") from exc
    else:
        raise AssertionError("unsafe SIP event was accepted")


base_cdr: dict[str, object] = {
    "schema_version": "1.0",
    "source_record_id": "cdr-negative-fixture",
    "observed_at": "2026-08-01T19:04:00Z",
    "direction": "outbound",
    "disposition": "failed",
    "sip_code": 503,
    "carrier_id": "carrier-fixture-a",
    "destination_country": "US",
    "duration_seconds": 0,
}

for field, value, expected in (
    ("caller_id", "+1 555 010 0200", "prohibited sensitive field"),
    ("src", "5550100200", "prohibited sensitive field"),
    ("notes", "synthetic note", "unsupported field"),
    ("metadata", {"safe": "no"}, "unsupported field"),
):
    unsafe = dict(base_cdr)
    unsafe[field] = value
    assert_cdr_rejected(unsafe, expected)

unsafe = dict(base_cdr)
unsafe["carrier_id"] = "18005550199"
assert_cdr_rejected(unsafe, "opaque lowercase identifier")

unsafe = dict(base_cdr)
unsafe["source_record_id"] = "cdr-123456789"
assert_cdr_rejected(unsafe, "telephone or account number")

unsafe = dict(base_cdr)
unsafe["carrier_id"] = "sip:carrier@example.invalid"
assert_cdr_rejected(unsafe, "prohibited address or URI data")

unsafe = dict(base_cdr)
unsafe["carrier_id"] = "192.0.2.10"
assert_cdr_rejected(unsafe, "prohibited address or URI data")

unsafe = dict(base_cdr)
unsafe["observed_at"] = "2026-08-01T19:04:00+00:00"
assert_cdr_rejected(unsafe, "RFC 3339 UTC timestamp")

unsafe = dict(base_cdr)
unsafe["destination_country"] = "CAN"
assert_cdr_rejected(unsafe, "two-letter code")

unsafe = dict(base_cdr)
unsafe["duration_seconds"] = -1
assert_cdr_rejected(unsafe, "outside the accepted range")

unsafe = dict(base_cdr)
unsafe["sip_code"] = 700
assert_cdr_rejected(unsafe, "between 100 and 699")

unsafe = dict(base_cdr)
unsafe["schema_version"] = "2.0"
assert_cdr_rejected(unsafe, "unsupported schema_version")

base_sip: dict[str, object] = {
    "schema_version": "1.0",
    "source_record_id": "sip-negative-fixture",
    "observed_at": "2026-08-01T19:05:00Z",
    "event_type": "invite_final",
    "direction": "inbound",
    "sip_code": 403,
    "duration_seconds": 0,
}

unsafe_sip = dict(base_sip)
unsafe_sip["headers"] = "Authorization: secret"
assert_sip_rejected(unsafe_sip, "prohibited sensitive field")

unsafe_sip = dict(base_sip)
unsafe_sip["event_type"] = "INVITE FINAL"
assert_sip_rejected(unsafe_sip, "lowercase operational slug")

unsafe_sip = dict(base_sip)
unsafe_sip["final_disposition"] = "root_cause_guess"
assert_sip_rejected(unsafe_sip, "unsupported call disposition")

assert len(adapt_sanitized_cdr_rows([cdr_example, base_cdr])) == 2
assert len(adapt_sanitized_sip_events([sip_example, base_sip])) == 2

try:
    adapt_sanitized_cdr_rows([cdr_example, unsafe])
except SanitizedAdapterError as exc:
    assert "CDR record 1 rejected" in str(exc)
else:
    raise AssertionError("invalid CDR batch was partially accepted")

try:
    adapt_sanitized_sip_events([sip_example, unsafe_sip])
except SanitizedAdapterError as exc:
    assert "SIP event 1 rejected" in str(exc)
else:
    raise AssertionError("invalid SIP batch was partially accepted")

doc_source = DOC.read_text(encoding="utf-8")
for marker in (
    "Fail-closed boundary",
    "Sanitized CDR contract",
    "Sanitized SIP-event contract",
    "Explicitly rejected data",
    "No live collector activation",
):
    if marker not in doc_source:
        raise SystemExit(f"sanitized adapter documentation missing marker: {marker}")

print("telephony sanitized adapter validation passed")
