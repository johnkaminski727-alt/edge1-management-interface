#!/usr/bin/env python3
"""Privacy-minimized, hash-chained audit events for analytics report generation.

This module records that an already-generated aggregate report was produced. It
does not generate reports, read telephony sources, contact services, or expose a
write API. The audit log is an append-only JSONL file protected by an exclusive
file lock and a SHA-256 event chain.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "1.0"
EVENT_TYPE = "telephony_analytics_report_generated"
PRIVACY_PROFILE = "aggregate_no_customer_identifiers"
ZERO_HASH = "0" * 64
MAX_RECORD_COUNT = 1_000_000_000

REPORT_KINDS = {
    "health_summary",
    "call_summary",
    "interconnect_summary",
    "combined_summary",
}

BASE_FIELDS = {
    "schema_version",
    "event_type",
    "event_id",
    "occurred_at",
    "report_id",
    "report_kind",
    "generator_id",
    "repository_revision",
    "input_manifest_sha256",
    "output_sha256",
    "aggregate_record_count",
    "privacy_profile",
}
CHAIN_FIELDS = {"previous_event_sha256", "event_sha256"}
ALL_FIELDS = BASE_FIELDS | CHAIN_FIELDS

SAFE_ID_RE = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
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


class ReportAuditError(ValueError):
    """Raised when an event or audit log violates the bounded contract."""


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _safe_id(value: Any, field_name: str) -> str:
    token = str(value or "").strip().lower()
    if not SAFE_ID_RE.fullmatch(token):
        raise ReportAuditError(f"{field_name} must be an opaque lowercase identifier")
    if LONG_DIGIT_RE.search(token):
        raise ReportAuditError(f"{field_name} must not contain a telephone or account number")
    return token


def _sha256(value: Any, field_name: str) -> str:
    token = str(value or "").strip().lower()
    if not SHA256_RE.fullmatch(token):
        raise ReportAuditError(f"{field_name} must be a lowercase SHA-256 digest")
    return token


def _git_revision(value: Any) -> str:
    token = str(value or "").strip().lower()
    if not GIT_SHA_RE.fullmatch(token):
        raise ReportAuditError("repository_revision must be a full lowercase Git commit SHA")
    return token


def _timestamp(value: Any) -> str:
    text = str(value or "").strip()
    if not UTC_TIMESTAMP_RE.fullmatch(text):
        raise ReportAuditError("occurred_at must be an RFC 3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ReportAuditError("occurred_at must be an RFC 3339 UTC timestamp") from exc
    return parsed.isoformat().replace("+00:00", "Z")


def _bounded_count(value: Any) -> int:
    if isinstance(value, bool):
        raise ReportAuditError("aggregate_record_count must be an integer")
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise ReportAuditError("aggregate_record_count must be an integer") from exc
    if count < 0 or count > MAX_RECORD_COUNT:
        raise ReportAuditError("aggregate_record_count is outside the accepted range")
    return count


def _reject_sensitive_text(event: Mapping[str, Any]) -> None:
    for key, value in event.items():
        if not isinstance(value, (str, int)):
            raise ReportAuditError(f"{key} must be a scalar string or integer")
        if not isinstance(value, str):
            continue
        if CONTROL_RE.search(value):
            raise ReportAuditError(f"{key} contains control characters")
        if EMAIL_RE.search(value) or URI_RE.search(value) or IPV4_RE.search(value):
            raise ReportAuditError(f"{key} contains prohibited address or URI data")


def normalize_base_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize an event before chain fields are added."""
    if not isinstance(event, Mapping):
        raise ReportAuditError("event must be a mapping")
    if set(event) != BASE_FIELDS:
        missing = sorted(BASE_FIELDS - set(event))
        extra = sorted(set(event) - BASE_FIELDS)
        raise ReportAuditError(f"event fields do not match contract; missing={missing} extra={extra}")

    normalized = {
        "schema_version": str(event["schema_version"]),
        "event_type": str(event["event_type"]),
        "event_id": _safe_id(event["event_id"], "event_id"),
        "occurred_at": _timestamp(event["occurred_at"]),
        "report_id": _safe_id(event["report_id"], "report_id"),
        "report_kind": str(event["report_kind"]).strip().lower(),
        "generator_id": _safe_id(event["generator_id"], "generator_id"),
        "repository_revision": _git_revision(event["repository_revision"]),
        "input_manifest_sha256": _sha256(event["input_manifest_sha256"], "input_manifest_sha256"),
        "output_sha256": _sha256(event["output_sha256"], "output_sha256"),
        "aggregate_record_count": _bounded_count(event["aggregate_record_count"]),
        "privacy_profile": str(event["privacy_profile"]),
    }

    if normalized["schema_version"] != SCHEMA_VERSION:
        raise ReportAuditError("unsupported schema_version")
    if normalized["event_type"] != EVENT_TYPE:
        raise ReportAuditError("unsupported event_type")
    if normalized["report_kind"] not in REPORT_KINDS:
        raise ReportAuditError("unsupported report_kind")
    if normalized["privacy_profile"] != PRIVACY_PROFILE:
        raise ReportAuditError("unsupported privacy_profile")

    _reject_sensitive_text(normalized)
    return normalized


def event_hash(event_without_hash: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(event_without_hash).encode("ascii")).hexdigest()


def chained_event(base_event: Mapping[str, Any], previous_hash: str) -> dict[str, Any]:
    normalized = normalize_base_event(base_event)
    previous = _sha256(previous_hash, "previous_event_sha256")
    value = dict(normalized)
    value["previous_event_sha256"] = previous
    value["event_sha256"] = event_hash(value)
    return value


def validate_chained_event(event: Mapping[str, Any], expected_previous_hash: str) -> dict[str, Any]:
    if not isinstance(event, Mapping) or set(event) != ALL_FIELDS:
        raise ReportAuditError("chained event fields do not match contract")
    base = {key: event[key] for key in BASE_FIELDS}
    normalized = normalize_base_event(base)
    previous = _sha256(event["previous_event_sha256"], "previous_event_sha256")
    if previous != expected_previous_hash:
        raise ReportAuditError("previous_event_sha256 does not match the audit chain")
    expected = dict(normalized)
    expected["previous_event_sha256"] = previous
    actual_hash = _sha256(event["event_sha256"], "event_sha256")
    calculated_hash = event_hash(expected)
    if actual_hash != calculated_hash:
        raise ReportAuditError("event_sha256 does not match the event content")
    expected["event_sha256"] = actual_hash
    return expected


def _read_locked_events(fd: int) -> tuple[list[dict[str, Any]], str]:
    os.lseek(fd, 0, os.SEEK_SET)
    with os.fdopen(os.dup(fd), "r", encoding="utf-8", errors="strict") as handle:
        lines = handle.readlines()

    events: list[dict[str, Any]] = []
    previous = ZERO_HASH
    for line_number, line in enumerate(lines, start=1):
        if not line.endswith("\n"):
            raise ReportAuditError(f"audit line {line_number} is not newline-terminated")
        if not line.strip():
            raise ReportAuditError(f"audit line {line_number} is empty")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReportAuditError(f"audit line {line_number} is not valid JSON") from exc
        event = validate_chained_event(value, previous)
        events.append(event)
        previous = event["event_sha256"]
    return events, previous


def _open_audit_log(path: Path, create: bool) -> int:
    if not path.is_absolute():
        raise ReportAuditError("audit log path must be absolute")
    if path.suffix != ".jsonl":
        raise ReportAuditError("audit log must use a .jsonl suffix")
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise ReportAuditError("audit log parent must be an existing non-symlink directory")
    if path.is_symlink():
        raise ReportAuditError("audit log must not be a symlink")

    flags = os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW
    if create:
        flags |= os.O_APPEND | os.O_CREAT
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise ReportAuditError(f"could not open audit log: {exc}") from exc

    metadata = os.fstat(fd)
    if not stat.S_ISREG(metadata.st_mode):
        os.close(fd)
        raise ReportAuditError("audit log must be a regular file")
    if metadata.st_uid != os.geteuid():
        os.close(fd)
        raise ReportAuditError("audit log must be owned by the current effective user")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        os.close(fd)
        raise ReportAuditError("audit log permissions must not grant group or other access")
    return fd


def verify_audit_log(path: Path) -> dict[str, Any]:
    """Verify every event and return a privacy-minimized chain summary."""
    fd = _open_audit_log(path, create=False)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH)
        events, last_hash = _read_locked_events(fd)
        return {
            "event_count": len(events),
            "last_event_sha256": last_hash,
            "chain_valid": True,
        }
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def append_audit_event(path: Path, base_event: Mapping[str, Any]) -> dict[str, Any]:
    """Validate, chain, append, flush, and return one audit event."""
    normalized = normalize_base_event(base_event)
    fd = _open_audit_log(path, create=True)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        _events, previous_hash = _read_locked_events(fd)
        event = chained_event(normalized, previous_hash)
        encoded = (canonical_json(event) + "\n").encode("ascii")
        os.write(fd, encoded)
        os.fsync(fd)
        return event
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
