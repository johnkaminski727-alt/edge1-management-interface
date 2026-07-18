#!/usr/bin/env python3
"""Validate WW.CX records-evidence metadata, objects, and SHA-256 manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RECORD_ID = re.compile(r"^WWCX-[A-Z0-9][A-Z0-9._-]{2,127}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
EVENT_TYPES = {
    "capture",
    "validation",
    "fixity_check",
    "migration",
    "restore_test",
    "disposition_review",
    "transfer",
}
OUTCOMES = {"success", "failure", "warning"}
SENSITIVITIES = {"public", "internal", "confidential", "restricted"}
DISPOSITIONS = {"review", "transfer", "destroy", "permanent"}


class EvidenceValidationError(ValueError):
    """Raised when an evidence package violates a required control."""


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceValidationError(f"{label} must be an object")
    return value


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceValidationError(f"{label} must be a non-empty string")
    return value


def require_exact_keys(
    value: dict[str, Any],
    *,
    required: set[str],
    optional: set[str],
    label: str,
) -> None:
    missing = sorted(required.difference(value))
    unexpected = sorted(set(value).difference(required | optional))
    if missing:
        raise EvidenceValidationError(f"{label} missing required keys: {missing}")
    if unexpected:
        raise EvidenceValidationError(f"{label} has unexpected keys: {unexpected}")


def parse_utc(value: Any, label: str) -> datetime:
    text = require_text(value, label)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise EvidenceValidationError(f"{label} must be an ISO 8601 date-time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise EvidenceValidationError(f"{label} must include a UTC offset")
    return parsed


def validate_relative_path(value: Any, label: str) -> str:
    text = require_text(value, label)
    if "\\" in text:
        raise EvidenceValidationError(f"{label} must use forward slashes")
    if text.startswith("/"):
        raise EvidenceValidationError(f"{label} must be relative")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise EvidenceValidationError(f"{label} contains an unsafe path segment")
    return text


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_package_file(package_root: Path, relative: str) -> Path:
    root = package_root.resolve()
    candidate = (root / relative).resolve()
    if candidate == root or root not in candidate.parents:
        raise EvidenceValidationError(f"object path leaves package root: {relative}")
    if not candidate.is_file():
        raise EvidenceValidationError(f"object file is missing: {relative}")
    return candidate


def validate_source(value: Any) -> None:
    source = require_mapping(value, "authoritative_source")
    require_exact_keys(
        source,
        required={"system", "location", "responsible_role"},
        optional={"version"},
        label="authoritative_source",
    )
    for key in ("system", "location", "responsible_role"):
        require_text(source[key], f"authoritative_source.{key}")
    if "version" in source:
        require_text(source["version"], "authoritative_source.version")


def validate_retention(value: Any) -> None:
    retention = require_mapping(value, "retention_rule")
    require_exact_keys(
        retention,
        required={"schedule_id", "trigger", "minimum_years", "disposition", "legal_hold"},
        optional=set(),
        label="retention_rule",
    )
    require_text(retention["schedule_id"], "retention_rule.schedule_id")
    require_text(retention["trigger"], "retention_rule.trigger")
    years = retention["minimum_years"]
    if isinstance(years, bool) or not isinstance(years, int) or years < 0:
        raise EvidenceValidationError("retention_rule.minimum_years must be a non-negative integer")
    if retention["disposition"] not in DISPOSITIONS:
        raise EvidenceValidationError("retention_rule.disposition is unsupported")
    if not isinstance(retention["legal_hold"], bool):
        raise EvidenceValidationError("retention_rule.legal_hold must be boolean")
    if retention["legal_hold"] and retention["disposition"] == "destroy":
        raise EvidenceValidationError("a record on legal hold cannot have destroy disposition")


def validate_objects(value: Any, package_root: Path | None) -> dict[str, str]:
    if not isinstance(value, list) or not value:
        raise EvidenceValidationError("objects must be a non-empty array")
    digests: dict[str, str] = {}
    for index, raw in enumerate(value):
        item = require_mapping(raw, f"objects[{index}]")
        require_exact_keys(
            item,
            required={"path", "media_type", "size_bytes", "sha256"},
            optional=set(),
            label=f"objects[{index}]",
        )
        relative = validate_relative_path(item["path"], f"objects[{index}].path")
        if relative in digests:
            raise EvidenceValidationError(f"duplicate object path: {relative}")
        require_text(item["media_type"], f"objects[{index}].media_type")
        size = item["size_bytes"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise EvidenceValidationError(f"objects[{index}].size_bytes must be non-negative")
        digest = item["sha256"]
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise EvidenceValidationError(f"objects[{index}].sha256 is invalid")
        digests[relative] = digest
        if package_root is not None:
            path = resolve_package_file(package_root, relative)
            if path.stat().st_size != size:
                raise EvidenceValidationError(f"object size mismatch: {relative}")
            if sha256_file(path) != digest:
                raise EvidenceValidationError(f"object digest mismatch: {relative}")
    return digests


def validate_events(value: Any) -> None:
    if not isinstance(value, list) or not value:
        raise EvidenceValidationError("events must be a non-empty array")
    for index, raw in enumerate(value):
        event = require_mapping(raw, f"events[{index}]")
        require_exact_keys(
            event,
            required={"event_type", "event_utc", "agent", "agent_role", "outcome"},
            optional={"details"},
            label=f"events[{index}]",
        )
        if event["event_type"] not in EVENT_TYPES:
            raise EvidenceValidationError(f"events[{index}].event_type is unsupported")
        parse_utc(event["event_utc"], f"events[{index}].event_utc")
        require_text(event["agent"], f"events[{index}].agent")
        require_text(event["agent_role"], f"events[{index}].agent_role")
        if event["outcome"] not in OUTCOMES:
            raise EvidenceValidationError(f"events[{index}].outcome is unsupported")
        if "details" in event:
            require_text(event["details"], f"events[{index}].details")


def validate_record_data(data: Any, package_root: Path | None = None) -> dict[str, str]:
    record = require_mapping(data, "record")
    require_exact_keys(
        record,
        required={
            "record_id",
            "title",
            "record_class",
            "created_utc",
            "authoritative_source",
            "retention_rule",
            "sensitivity",
            "objects",
            "events",
        },
        optional={"notes"},
        label="record",
    )
    record_id = require_text(record["record_id"], "record_id")
    if not RECORD_ID.fullmatch(record_id):
        raise EvidenceValidationError("record_id does not match the WWCX identifier profile")
    require_text(record["title"], "title")
    require_text(record["record_class"], "record_class")
    parse_utc(record["created_utc"], "created_utc")
    validate_source(record["authoritative_source"])
    validate_retention(record["retention_rule"])
    if record["sensitivity"] not in SENSITIVITIES:
        raise EvidenceValidationError("sensitivity is unsupported")
    digests = validate_objects(record["objects"], package_root)
    validate_events(record["events"])
    if "notes" in record:
        require_text(record["notes"], "notes")
    return digests


def load_record(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceValidationError(f"cannot load record {path}: {exc}") from exc


def load_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EvidenceValidationError(f"cannot load manifest {path}: {exc}") from exc
    for number, line in enumerate(lines, 1):
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([a-f0-9]{64})  (.+)", line)
        if not match:
            raise EvidenceValidationError(f"manifest line {number} is malformed")
        digest, raw_path = match.groups()
        relative = validate_relative_path(raw_path, f"manifest line {number} path")
        if relative in entries:
            raise EvidenceValidationError(f"duplicate manifest path: {relative}")
        entries[relative] = digest
    if not entries:
        raise EvidenceValidationError("manifest must contain at least one entry")
    return entries


def validate_manifest(
    manifest_path: Path,
    package_root: Path,
    record_digests: dict[str, str],
) -> None:
    entries = load_manifest(manifest_path)
    if entries != record_digests:
        missing = sorted(set(record_digests).difference(entries))
        extra = sorted(set(entries).difference(record_digests))
        mismatched = sorted(
            path for path in set(entries).intersection(record_digests)
            if entries[path] != record_digests[path]
        )
        raise EvidenceValidationError(
            f"manifest and record differ; missing={missing}, extra={extra}, mismatched={mismatched}"
        )
    for relative, digest in entries.items():
        if sha256_file(resolve_package_file(package_root, relative)) != digest:
            raise EvidenceValidationError(f"manifest digest mismatch: {relative}")


def validate_package(record_path: Path, package_root: Path, manifest_path: Path) -> None:
    digests = validate_record_data(load_record(record_path), package_root)
    validate_manifest(manifest_path, package_root, digests)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path, help="JSON evidence record")
    parser.add_argument("--package-root", type=Path, required=True, help="root containing preserved objects")
    parser.add_argument("--manifest", type=Path, required=True, help="SHA-256 manifest")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        validate_package(args.record, args.package_root, args.manifest)
    except EvidenceValidationError as exc:
        print(f"records evidence validation failed: {exc}", file=sys.stderr)
        return 1
    print("records evidence validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
