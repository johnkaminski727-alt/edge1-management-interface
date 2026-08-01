#!/usr/bin/env python3
"""Offline aggregate telephony report generation with fail-closed file output.

The generator accepts only an already-aggregated, privacy-minimized snapshot. It
performs no network, database, PBX, carrier, service-control, scheduler, or live
source access. A successful write creates a new owner-only bundle and an audit
event candidate; it never appends to a live audit log or overwrites an artifact.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from telephony_anomaly_indicators import evaluate_anomaly_indicators

SCHEMA_VERSION = "1.0"
REPORT_TYPE = "telephony_analytics_aggregate_report"
REPORT_KIND = "combined_summary"
PRIVACY_PROFILE = "aggregate_no_customer_identifiers"
SOURCE_CONTRACT = "already_aggregated_summaries_only"
GENERATOR_ID = "telephony.aggregate.report.v1"
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_REPORT_BYTES = 4 * 1024 * 1024

INPUT_FIELDS = {
    "schema_version",
    "report_id",
    "generated_at",
    "repository_revision",
    "report_kind",
    "health_summary",
    "call_summary",
    "interconnect_summary",
}

SAFE_ID_RE = re.compile(r"^[a-z][a-z0-9._-]{0,47}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
UTC_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z$"
)
LONG_DIGIT_RE = re.compile(r"[0-9]{7,}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URI_RE = re.compile(r"\b(?:sip|sips|tel|http|https):", re.IGNORECASE)
IPV4_RE = re.compile(r"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class AggregateReportError(ValueError):
    """Raised when input or output violates the aggregate report contract."""


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _safe_id(value: Any, field_name: str) -> str:
    token = str(value or "").strip().lower()
    if not SAFE_ID_RE.fullmatch(token):
        raise AggregateReportError(f"{field_name} must be an opaque lowercase identifier")
    if LONG_DIGIT_RE.search(token):
        raise AggregateReportError(f"{field_name} must not contain a telephone or account number")
    return token


def _timestamp(value: Any) -> str:
    text = str(value or "").strip()
    if not UTC_TIMESTAMP_RE.fullmatch(text):
        raise AggregateReportError("generated_at must be an RFC 3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise AggregateReportError("generated_at must be an RFC 3339 UTC timestamp") from exc
    return parsed.isoformat().replace("+00:00", "Z")


def _git_revision(value: Any) -> str:
    token = str(value or "").strip().lower()
    if not GIT_SHA_RE.fullmatch(token):
        raise AggregateReportError("repository_revision must be a full lowercase Git commit SHA")
    return token


def _json_copy(value: Any, field_name: str) -> Any:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        copied = json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AggregateReportError(f"{field_name} must contain finite JSON values only") from exc
    if CONTROL_RE.search(encoded) or EMAIL_RE.search(encoded) or URI_RE.search(encoded) or IPV4_RE.search(encoded):
        raise AggregateReportError(f"{field_name} contains prohibited address or URI data")
    return copied


def normalize_report_input(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize one already-aggregated report request."""
    if not isinstance(value, Mapping):
        raise AggregateReportError("report input must be a mapping")
    if set(value) != INPUT_FIELDS:
        missing = sorted(INPUT_FIELDS - set(value))
        extra = sorted(set(value) - INPUT_FIELDS)
        raise AggregateReportError(
            f"report input fields do not match contract; missing={missing} extra={extra}"
        )
    if str(value["schema_version"]) != SCHEMA_VERSION:
        raise AggregateReportError("unsupported schema_version")
    report_kind = str(value["report_kind"]).strip().lower()
    if report_kind != REPORT_KIND:
        raise AggregateReportError("unsupported report_kind")

    health = _json_copy(value["health_summary"], "health_summary")
    calls = _json_copy(value["call_summary"], "call_summary")
    interconnects = _json_copy(value["interconnect_summary"], "interconnect_summary")

    try:
        evaluate_anomaly_indicators(health, calls, interconnects)
    except (TypeError, ValueError) as exc:
        raise AggregateReportError(f"aggregate summaries failed validation: {exc}") from exc

    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": _safe_id(value["report_id"], "report_id"),
        "generated_at": _timestamp(value["generated_at"]),
        "repository_revision": _git_revision(value["repository_revision"]),
        "report_kind": REPORT_KIND,
        "health_summary": health,
        "call_summary": calls,
        "interconnect_summary": interconnects,
    }


def input_manifest_sha256(normalized_input: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(normalized_input).encode("ascii")).hexdigest()


def build_report(normalized_input: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deterministic report from a normalized aggregate input."""
    value = normalize_report_input(normalized_input)
    anomalies = evaluate_anomaly_indicators(
        value["health_summary"],
        value["call_summary"],
        value["interconnect_summary"],
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "report_type": REPORT_TYPE,
        "report_id": value["report_id"],
        "generated_at": value["generated_at"],
        "repository_revision": value["repository_revision"],
        "report_kind": REPORT_KIND,
        "privacy_profile": PRIVACY_PROFILE,
        "source_contract": SOURCE_CONTRACT,
        "health_summary": value["health_summary"],
        "call_summary": value["call_summary"],
        "interconnect_summary": value["interconnect_summary"],
        "anomaly_summary": anomalies,
        "safety": {
            "live_source_access": False,
            "audit_log_append": False,
            "notification_dispatch": False,
            "traffic_enforcement": False,
            "route_change": False,
            "service_control": False,
            "call_origination": False,
            "dtmf_transmission": False,
        },
    }
    encoded = canonical_json(report).encode("ascii")
    if len(encoded) > MAX_REPORT_BYTES:
        raise AggregateReportError("generated report exceeds the accepted size limit")
    return report


def _markdown_value(value: Any) -> str:
    if value is None:
        return "not available"
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AggregateReportError("markdown value must be finite")
        text = f"{value:g}"
    else:
        text = str(value)
    if CONTROL_RE.search(text) or "\n" in text or "\r" in text:
        raise AggregateReportError("markdown value contains unsupported control text")
    return text.replace("|", "\\|")


def _count_table(title: str, values: Mapping[str, Any]) -> list[str]:
    lines = [f"### {title}", "", "| Aggregate key | Count |", "|---|---:|"]
    if not values:
        lines.append("| none | 0 |")
    else:
        for key in sorted(values):
            lines.append(f"| `{_markdown_value(key)}` | {_markdown_value(values[key])} |")
    lines.append("")
    return lines


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render a deterministic human-readable view of a generated report."""
    value = build_report({
        "schema_version": report["schema_version"],
        "report_id": report["report_id"],
        "generated_at": report["generated_at"],
        "repository_revision": report["repository_revision"],
        "report_kind": report["report_kind"],
        "health_summary": report["health_summary"],
        "call_summary": report["call_summary"],
        "interconnect_summary": report["interconnect_summary"],
    })
    health = value["health_summary"]
    calls = value["call_summary"]
    interconnects = value["interconnect_summary"]
    anomalies = value["anomaly_summary"]

    lines = [
        "# Telephony Aggregate Analytics Report",
        "",
        f"- Report ID: `{_markdown_value(value['report_id'])}`",
        f"- Generated at: `{_markdown_value(value['generated_at'])}`",
        f"- Repository revision: `{_markdown_value(value['repository_revision'])}`",
        f"- Privacy profile: `{PRIVACY_PROFILE}`",
        f"- Source contract: `{SOURCE_CONTRACT}`",
        "",
        "## Platform health",
        "",
        f"- Overall status: **{_markdown_value(health['overall_status'])}**",
        f"- Weighted score: **{_markdown_value(health['score'])}**",
        "",
        "| Component | State |",
        "|---|---|",
    ]
    for component in sorted(health["components"]):
        lines.append(
            f"| `{_markdown_value(component)}` | `{_markdown_value(health['components'][component])}` |"
        )

    lines.extend([
        "",
        "## Call aggregates",
        "",
        f"- Calls: **{_markdown_value(calls['calls_total'])}**",
        f"- Answered: **{_markdown_value(calls['calls_answered'])}**",
        f"- Answer rate: **{_markdown_value(calls['answer_rate_percent'])}%**",
        f"- Total duration: **{_markdown_value(calls['duration_seconds_total'])} seconds**",
        f"- Average duration: **{_markdown_value(calls['duration_seconds_average'])} seconds**",
        "",
    ])
    lines.extend(_count_table("Dispositions", calls["dispositions"]))
    lines.extend(_count_table("SIP response codes", calls["sip_codes"]))
    lines.extend(_count_table("Failure classes", calls["failure_classes"]))
    lines.extend(_count_table("Sanitized carrier aggregates", calls["carriers"]))
    lines.extend(_count_table("Destination-country aggregates", calls["destination_countries"]))

    lines.extend([
        "## Interconnect aggregates",
        "",
        f"- Interconnects: **{_markdown_value(interconnects['interconnects_total'])}**",
        f"- Attention required: **{_markdown_value(interconnects['attention_required'])}**",
        f"- Average latency: **{_markdown_value(interconnects['latency_ms_average'])} ms**",
        f"- Maximum latency: **{_markdown_value(interconnects['latency_ms_max'])} ms**",
        "",
    ])
    lines.extend(_count_table("Interconnect states", interconnects["states"]))

    lines.extend([
        "## Informational anomaly indicators",
        "",
        f"Overall state: **{_markdown_value(anomalies['overall_state'])}**",
        "",
        "| Indicator | State | Observed | Unit | Sample |",
        "|---|---|---:|---|---:|",
    ])
    for item in anomalies["indicators"]:
        lines.append(
            "| `{}` | `{}` | {} | `{}` | {} |".format(
                _markdown_value(item["id"]),
                _markdown_value(item["state"]),
                _markdown_value(item["observed_value"]),
                _markdown_value(item["unit"]),
                _markdown_value(item["sample_size"]),
            )
        )

    lines.extend([
        "",
        "## Safety boundary",
        "",
        "This report was generated from already-aggregated summaries only. It did not access a live source, append an audit log, dispatch a notification, enforce traffic, change a route, control a service, originate a call, or transmit DTMF.",
        "",
    ])
    return "\n".join(lines)


def audit_input_for_report(
    report: Mapping[str, Any],
    input_sha256: str,
    output_sha256: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", input_sha256):
        raise AggregateReportError("input manifest hash must be a lowercase SHA-256 digest")
    if not re.fullmatch(r"[0-9a-f]{64}", output_sha256):
        raise AggregateReportError("output hash must be a lowercase SHA-256 digest")
    calls = report["call_summary"]["calls_total"]
    interconnects = report["interconnect_summary"]["interconnects_total"]
    return {
        "schema_version": SCHEMA_VERSION,
        "event_type": "telephony_analytics_report_generated",
        "event_id": f"report.{report['report_id']}",
        "occurred_at": report["generated_at"],
        "report_id": report["report_id"],
        "report_kind": REPORT_KIND,
        "generator_id": GENERATOR_ID,
        "repository_revision": report["repository_revision"],
        "input_manifest_sha256": input_sha256,
        "output_sha256": output_sha256,
        "aggregate_record_count": int(calls) + int(interconnects),
        "privacy_profile": PRIVACY_PROFILE,
    }


def _write_exclusive(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise AggregateReportError(f"could not create report artifact {path.name}: {exc}") from exc
    try:
        offset = 0
        while offset < len(data):
            written = os.write(fd, data[offset:])
            if written <= 0:
                raise AggregateReportError(f"short write while creating {path.name}")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)


def write_report_bundle(
    output_dir: Path,
    report: Mapping[str, Any],
    input_sha256: str,
) -> dict[str, Any]:
    """Create a new owner-only report bundle without overwriting any path."""
    if not output_dir.is_absolute():
        raise AggregateReportError("output directory must be absolute")
    if output_dir.exists() or output_dir.is_symlink():
        raise AggregateReportError("output directory must not already exist")
    parent = output_dir.parent
    if not parent.is_dir() or parent.is_symlink():
        raise AggregateReportError("output parent must be an existing non-symlink directory")

    normalized_report = build_report({
        "schema_version": report["schema_version"],
        "report_id": report["report_id"],
        "generated_at": report["generated_at"],
        "repository_revision": report["repository_revision"],
        "report_kind": report["report_kind"],
        "health_summary": report["health_summary"],
        "call_summary": report["call_summary"],
        "interconnect_summary": report["interconnect_summary"],
    })
    report_json = (canonical_json(normalized_report) + "\n").encode("ascii")
    report_markdown = render_markdown(normalized_report).encode("utf-8")
    output_hash = hashlib.sha256(report_json).hexdigest()
    audit_input = audit_input_for_report(normalized_report, input_sha256, output_hash)
    audit_json = (canonical_json(audit_input) + "\n").encode("ascii")

    artifacts = {
        "report.json": report_json,
        "report.md": report_markdown,
        "report-audit-input.json": audit_json,
    }
    checksums = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in sorted(artifacts.items())
    ).encode("ascii")
    artifacts["SHA256SUMS"] = checksums

    created: list[Path] = []
    directory_created = False
    try:
        os.mkdir(output_dir, 0o700)
        directory_created = True
        for name in ("report.json", "report.md", "report-audit-input.json", "SHA256SUMS"):
            path = output_dir / name
            _write_exclusive(path, artifacts[name])
            created.append(path)
        directory_fd = os.open(output_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                pass
        if directory_created:
            try:
                output_dir.rmdir()
            except OSError:
                pass
        raise

    metadata = output_dir.stat()
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise AggregateReportError("report bundle directory permissions are not owner-only")
    for path in created:
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode != 0o600 or not path.is_file() or path.is_symlink():
            raise AggregateReportError(f"report artifact {path.name} failed permission validation")

    return {
        "output_directory": str(output_dir),
        "report_id": normalized_report["report_id"],
        "input_manifest_sha256": input_sha256,
        "report_sha256": output_hash,
        "audit_event_appended": False,
        "files": {
            name: hashlib.sha256(data).hexdigest()
            for name, data in sorted(artifacts.items())
        },
    }
