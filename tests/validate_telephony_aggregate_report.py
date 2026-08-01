#!/usr/bin/env python3
"""Validate offline aggregate telephony report generation and bundle safety."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from telephony_aggregate_report import (  # noqa: E402
    AggregateReportError,
    build_report,
    canonical_json,
    input_manifest_sha256,
    normalize_report_input,
    render_markdown,
    write_report_bundle,
)
from telephony_report_audit import normalize_base_event  # noqa: E402

MODULE = ROOT / "server" / "telephony_aggregate_report.py"
CLI = ROOT / "tools" / "telephony" / "generate_telephony_analytics_report.py"
INPUT_SCHEMA = ROOT / "schemas" / "telephony" / "analytics-report-input.schema.json"
REPORT_SCHEMA = ROOT / "schemas" / "telephony" / "analytics-report.schema.json"
INPUT_EXAMPLE = ROOT / "examples" / "telephony" / "analytics-report-input.example.json"
REPORT_EXAMPLE = ROOT / "examples" / "telephony" / "analytics-report.example.json"
DOC = ROOT / "docs" / "telephony" / "aggregate-report-generator.md"
ACCEPTANCE = ROOT / "docs" / "telephony" / "aggregate-report-generator-repository-acceptance-20260801.md"

for path in (
    MODULE, CLI, INPUT_SCHEMA, REPORT_SCHEMA, INPUT_EXAMPLE,
    REPORT_EXAMPLE, DOC, ACCEPTANCE,
):
    if not path.is_file():
        raise SystemExit(f"missing aggregate report asset: {path.relative_to(ROOT)}")

module_source = MODULE.read_text(encoding="utf-8")
cli_source = CLI.read_text(encoding="utf-8")
ast.parse(module_source, filename=str(MODULE))
ast.parse(cli_source, filename=str(CLI))

for marker in (
    "already_aggregated_summaries_only",
    "aggregate_no_customer_identifiers",
    "O_EXCL",
    "O_NOFOLLOW",
    "fsync",
    "audit_event_appended",
    "live_source_access",
    "call_origination",
    "dtmf_transmission",
):
    if marker not in module_source:
        raise SystemExit(f"aggregate report module missing marker: {marker}")

for marker in ("--validate-only", "MAX_INPUT_BYTES", "O_NOFOLLOW", "output_created"):
    if marker not in cli_source:
        raise SystemExit(f"aggregate report CLI missing marker: {marker}")

for forbidden in (
    "import socket",
    "import subprocess",
    "import sqlite3",
    "import urllib",
    "import requests",
    "systemctl",
    "asterisk -rx",
    "curl ",
    "mysql ",
    "psql ",
):
    if forbidden in module_source or forbidden in cli_source:
        raise SystemExit(f"aggregate report assets contain prohibited access path: {forbidden}")

input_schema = json.loads(INPUT_SCHEMA.read_text(encoding="utf-8"))
report_schema = json.loads(REPORT_SCHEMA.read_text(encoding="utf-8"))
assert input_schema["additionalProperties"] is False
assert report_schema["additionalProperties"] is False
assert report_schema["properties"]["privacy_profile"]["const"] == "aggregate_no_customer_identifiers"
assert report_schema["properties"]["source_contract"]["const"] == "already_aggregated_summaries_only"
for value in report_schema["properties"]["safety"]["properties"].values():
    assert value["const"] is False

input_example = json.loads(INPUT_EXAMPLE.read_text(encoding="utf-8"))
expected_report = json.loads(REPORT_EXAMPLE.read_text(encoding="utf-8"))
normalized = normalize_report_input(input_example)
report = build_report(normalized)
assert report == expected_report
assert report["anomaly_summary"]["overall_state"] == "critical"
assert report["safety"] == {
    "live_source_access": False,
    "audit_log_append": False,
    "notification_dispatch": False,
    "traffic_enforcement": False,
    "route_change": False,
    "service_control": False,
    "call_origination": False,
    "dtmf_transmission": False,
}

markdown = render_markdown(report)
for marker in (
    "# Telephony Aggregate Analytics Report",
    "## Platform health",
    "## Call aggregates",
    "## Interconnect aggregates",
    "## Informational anomaly indicators",
    "## Safety boundary",
    "already-aggregated summaries only",
):
    assert marker in markdown


def assert_rejected(value: dict[str, object], expected: str) -> None:
    try:
        normalize_report_input(value)
    except AggregateReportError as exc:
        if expected not in str(exc):
            raise AssertionError(f"unexpected rejection: {exc}") from exc
    else:
        raise AssertionError("unsafe aggregate report input was accepted")


unsafe = dict(input_example)
unsafe["caller_id"] = "+1 555 010 0200"
assert_rejected(unsafe, "fields do not match contract")

unsafe = dict(input_example)
unsafe["report_id"] = "report-123456789"
assert_rejected(unsafe, "telephone or account number")

unsafe = dict(input_example)
unsafe["generated_at"] = "2026-08-01"
assert_rejected(unsafe, "RFC 3339 UTC timestamp")

unsafe = dict(input_example)
unsafe["repository_revision"] = "deadbeef"
assert_rejected(unsafe, "full lowercase Git commit SHA")

unsafe = dict(input_example)
unsafe["report_kind"] = "raw_cdr_export"
assert_rejected(unsafe, "unsupported report_kind")

unsafe = json.loads(json.dumps(input_example))
unsafe["call_summary"]["calls_total"] = 21
assert_rejected(unsafe, "aggregate summaries failed validation")

unsafe = json.loads(json.dumps(input_example))
unsafe["call_summary"]["carriers"] = {"acct1234567": 20}
assert_rejected(unsafe, "aggregate summaries failed validation")

unsafe = json.loads(json.dumps(input_example))
unsafe["health_summary"]["score"] = float("nan")
assert_rejected(unsafe, "finite JSON values only")

spec = importlib.util.spec_from_file_location("telephony_report_cli", CLI)
assert spec is not None and spec.loader is not None
cli_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli_module)

with tempfile.TemporaryDirectory() as temp_dir:
    root = Path(temp_dir)
    input_path = root / "input.json"
    input_path.write_text(json.dumps(input_example), encoding="utf-8")
    assert cli_module.read_input(input_path) == input_example

    try:
        cli_module.read_input(Path("relative-input.json"))
    except AggregateReportError as exc:
        assert "absolute" in str(exc)
    else:
        raise AssertionError("relative input path was accepted")

    input_link = root / "input-link.json"
    input_link.symlink_to(input_path)
    try:
        cli_module.read_input(input_link)
    except AggregateReportError as exc:
        assert "symlink" in str(exc)
    else:
        raise AssertionError("symlink input was accepted")

    manifest_hash = input_manifest_sha256(normalized)
    output_dir = root / "bundle"
    summary = write_report_bundle(output_dir, report, manifest_hash)
    assert summary["audit_event_appended"] is False
    assert stat.S_IMODE(output_dir.stat().st_mode) == 0o700
    assert {path.name for path in output_dir.iterdir()} == {
        "report.json", "report.md", "report-audit-input.json", "SHA256SUMS"
    }
    for path in output_dir.iterdir():
        assert path.is_file() and not path.is_symlink()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    report_bytes = (output_dir / "report.json").read_bytes()
    assert report_bytes == (canonical_json(report) + "\n").encode("ascii")
    assert json.loads(report_bytes) == report
    assert (output_dir / "report.md").read_text(encoding="utf-8") == markdown

    audit_input = json.loads((output_dir / "report-audit-input.json").read_text(encoding="utf-8"))
    normalized_audit = normalize_base_event(audit_input)
    assert normalized_audit == audit_input
    assert audit_input["input_manifest_sha256"] == manifest_hash
    assert audit_input["output_sha256"] == hashlib.sha256(report_bytes).hexdigest()
    assert audit_input["aggregate_record_count"] == 22

    checksum_lines = (output_dir / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    assert len(checksum_lines) == 3
    for line in checksum_lines:
        digest, name = line.split("  ", 1)
        assert digest == hashlib.sha256((output_dir / name).read_bytes()).hexdigest()

    try:
        write_report_bundle(output_dir, report, manifest_hash)
    except AggregateReportError as exc:
        assert "must not already exist" in str(exc)
    else:
        raise AssertionError("existing report bundle was overwritten")

    try:
        write_report_bundle(Path("relative-bundle"), report, manifest_hash)
    except AggregateReportError as exc:
        assert "absolute" in str(exc)
    else:
        raise AssertionError("relative report bundle path was accepted")

    actual_parent = root / "actual-parent"
    actual_parent.mkdir()
    linked_parent = root / "linked-parent"
    linked_parent.symlink_to(actual_parent, target_is_directory=True)
    try:
        write_report_bundle(linked_parent / "bundle", report, manifest_hash)
    except AggregateReportError as exc:
        assert "non-symlink" in str(exc)
    else:
        raise AssertionError("symlink report parent was accepted")

for path in (DOC, ACCEPTANCE):
    text = path.read_text(encoding="utf-8")
    for marker in (
        "Already-aggregated input contract",
        "Owner-only bundle",
        "Audit-event candidate",
        "No scheduler or runtime activation",
        "No overwrite",
    ):
        if marker not in text:
            raise SystemExit(f"{path.name} missing marker: {marker}")

print("telephony aggregate report validation passed")
