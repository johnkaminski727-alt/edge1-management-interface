#!/usr/bin/env python3
"""Validate append-only privacy-minimized analytics report audit events."""
from __future__ import annotations

import ast
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from telephony_report_audit import (  # noqa: E402
    ZERO_HASH,
    ReportAuditError,
    append_audit_event,
    canonical_json,
    normalize_base_event,
    validate_chained_event,
    verify_audit_log,
)

MODULE = ROOT / "server" / "telephony_report_audit.py"
CLI = ROOT / "tools" / "telephony" / "append_analytics_report_audit.py"
INPUT_SCHEMA = ROOT / "schemas" / "telephony" / "analytics-report-audit-input.schema.json"
EVENT_SCHEMA = ROOT / "schemas" / "telephony" / "analytics-report-audit-event.schema.json"
INPUT_EXAMPLE = ROOT / "examples" / "telephony" / "analytics-report-audit-input.example.json"
EVENT_EXAMPLE = ROOT / "examples" / "telephony" / "analytics-report-audit-event.example.json"
DOC = ROOT / "docs" / "telephony" / "analytics-report-audit-events.md"

for path in (MODULE, CLI, INPUT_SCHEMA, EVENT_SCHEMA, INPUT_EXAMPLE, EVENT_EXAMPLE, DOC):
    if not path.is_file():
        raise SystemExit(f"missing report audit asset: {path.relative_to(ROOT)}")

module_source = MODULE.read_text(encoding="utf-8")
cli_source = CLI.read_text(encoding="utf-8")
ast.parse(module_source, filename=str(MODULE))
ast.parse(cli_source, filename=str(CLI))

for marker in (
    "O_APPEND",
    "O_NOFOLLOW",
    "flock",
    "LOCK_EX",
    "fsync",
    "previous_event_sha256",
    "event_sha256",
    "aggregate_no_customer_identifiers",
    "audit log permissions must not grant group or other access",
):
    if marker not in module_source:
        raise SystemExit(f"report audit module missing marker: {marker}")

for forbidden in (
    "import socket",
    "import subprocess",
    "import sqlite3",
    "import urllib",
    "import requests",
    "systemctl",
    "asterisk -rx",
    "mysql ",
    "psql ",
):
    if forbidden in module_source or forbidden in cli_source:
        raise SystemExit(f"report audit assets contain prohibited access path: {forbidden}")

for schema_path in (INPUT_SCHEMA, EVENT_SCHEMA):
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["privacy_profile"]["const"] == "aggregate_no_customer_identifiers"

input_example = json.loads(INPUT_EXAMPLE.read_text(encoding="utf-8"))
event_example = json.loads(EVENT_EXAMPLE.read_text(encoding="utf-8"))
normalized_example = normalize_base_event(input_example)
validated_example = validate_chained_event(event_example, ZERO_HASH)
assert validated_example["event_sha256"] == "0408234c30efe0f8dfeec7b7f16a8bf511062559a279bf523bd673de3f0be2c2"
assert {key: validated_example[key] for key in normalized_example} == normalized_example


def second_event() -> dict[str, object]:
    value = dict(input_example)
    value.update({
        "event_id": "report-event-beta",
        "occurred_at": "2026-08-01T19:46:00Z",
        "report_id": "report-fixture-beta",
        "report_kind": "health_summary",
        "input_manifest_sha256": "4" * 64,
        "output_sha256": "5" * 64,
        "aggregate_record_count": 5,
    })
    return value


def assert_rejected(event: dict[str, object], expected: str) -> None:
    try:
        normalize_base_event(event)
    except ReportAuditError as exc:
        if expected not in str(exc):
            raise AssertionError(f"unexpected rejection: {exc}") from exc
    else:
        raise AssertionError("unsafe report audit event was accepted")


unsafe = dict(input_example)
unsafe["caller_id"] = "+1 555 010 0200"
assert_rejected(unsafe, "event fields do not match contract")

unsafe = dict(input_example)
unsafe["event_id"] = "event-123456789"
assert_rejected(unsafe, "telephone or account number")

unsafe = dict(input_example)
unsafe["generator_id"] = "sip:generator@example.invalid"
assert_rejected(unsafe, "opaque lowercase identifier")

unsafe = dict(input_example)
unsafe["occurred_at"] = "2026-08-01"
assert_rejected(unsafe, "RFC 3339 UTC timestamp")

unsafe = dict(input_example)
unsafe["report_kind"] = "raw_cdr_export"
assert_rejected(unsafe, "unsupported report_kind")

unsafe = dict(input_example)
unsafe["aggregate_record_count"] = True
assert_rejected(unsafe, "must be an integer")

unsafe = dict(input_example)
unsafe["privacy_profile"] = "contains_customer_identifiers"
assert_rejected(unsafe, "unsupported privacy_profile")

with tempfile.TemporaryDirectory() as temp_dir:
    root = Path(temp_dir)
    audit_log = root / "telephony-report-audit.jsonl"

    first = append_audit_event(audit_log, input_example)
    first_bytes = audit_log.read_bytes()
    assert first["previous_event_sha256"] == ZERO_HASH
    assert first["event_sha256"] == event_example["event_sha256"]
    assert stat.S_IMODE(audit_log.stat().st_mode) == 0o600
    assert first_bytes == (canonical_json(first) + "\n").encode("ascii")

    first_summary = verify_audit_log(audit_log)
    assert first_summary == {
        "event_count": 1,
        "last_event_sha256": first["event_sha256"],
        "chain_valid": True,
    }

    second = append_audit_event(audit_log, second_event())
    assert second["previous_event_sha256"] == first["event_sha256"]
    assert audit_log.read_bytes().startswith(first_bytes)
    summary = verify_audit_log(audit_log)
    assert summary["event_count"] == 2
    assert summary["last_event_sha256"] == second["event_sha256"]
    assert summary["chain_valid"] is True

    lines = audit_log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0] == canonical_json(first)
    assert lines[1] == canonical_json(second)

    tampered = root / "tampered.jsonl"
    tampered_events = [json.loads(line) for line in lines]
    tampered_events[0]["aggregate_record_count"] = 13
    tampered.write_text("\n".join(canonical_json(value) for value in tampered_events) + "\n", encoding="utf-8")
    os.chmod(tampered, 0o600)
    try:
        verify_audit_log(tampered)
    except ReportAuditError as exc:
        assert "event_sha256 does not match" in str(exc)
    else:
        raise AssertionError("tampered audit log was accepted")

    incomplete = root / "incomplete.jsonl"
    incomplete.write_text(canonical_json(first), encoding="utf-8")
    os.chmod(incomplete, 0o600)
    try:
        verify_audit_log(incomplete)
    except ReportAuditError as exc:
        assert "not newline-terminated" in str(exc)
    else:
        raise AssertionError("unterminated audit line was accepted")

    insecure = root / "insecure.jsonl"
    insecure.write_bytes(first_bytes)
    os.chmod(insecure, 0o640)
    try:
        verify_audit_log(insecure)
    except ReportAuditError as exc:
        assert "permissions" in str(exc)
    else:
        raise AssertionError("group-readable audit log was accepted")

    symlink = root / "symlink.jsonl"
    symlink.symlink_to(audit_log)
    try:
        verify_audit_log(symlink)
    except ReportAuditError as exc:
        assert "symlink" in str(exc)
    else:
        raise AssertionError("symlink audit log was accepted")

try:
    append_audit_event(Path("relative-audit.jsonl"), input_example)
except ReportAuditError as exc:
    assert "absolute" in str(exc)
else:
    raise AssertionError("relative audit path was accepted")

for marker in (
    "Append-only contract",
    "Privacy-minimized event fields",
    "Hash-chain verification",
    "No report job or service activation",
):
    if marker not in DOC.read_text(encoding="utf-8"):
        raise SystemExit(f"report audit documentation missing marker: {marker}")

print("telephony report audit validation passed")
