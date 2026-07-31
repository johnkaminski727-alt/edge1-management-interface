#!/usr/bin/env python3
"""Validate an ordered CAP-CP message sequence without networking or delivery.

The probe applies CAP-CP structural validation, duplicate/replay checks, and
Alert/Update/Cancel reference-state checks. It emits only sanitized metadata.
Actual alerts remain blocked unless explicitly permitted for offline analysis.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from capcp_probe import CAP, MAX_XML_BYTES, validate_capcp

MessageKey = tuple[str, str, str]

@dataclass
class SequenceReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    records: list[dict[str, object]] = field(default_factory=list)
    active: dict[MessageKey, str] = field(default_factory=dict)

    @property
    def compatible(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, object]:
        active_records = [
            {"sender": key[0], "identifier": key[1], "sent": key[2], "state": state}
            for key, state in sorted(self.active.items())
            if state == "active"
        ]
        return {
            "compatible": self.compatible,
            "profile": "CAP-CP lifecycle and replay compatibility baseline",
            "operating_mode": "offline read-only test laboratory",
            "records": self.records,
            "active_alerts": active_records,
            "errors": self.errors,
            "warnings": self.warnings,
        }

def _text(parent: ET.Element, name: str) -> str:
    child = parent.find(CAP + name)
    return (child.text or "").strip() if child is not None else ""

def _parse_references(value: str) -> tuple[list[MessageKey], list[str]]:
    references: list[MessageKey] = []
    errors: list[str] = []
    for token in value.split():
        parts = token.split(",")
        if len(parts) != 3 or not all(parts):
            errors.append(f"invalid CAP reference triplet {token!r}")
            continue
        references.append((parts[0], parts[1], parts[2]))
    return references, errors

def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)

def validate_sequence(
    paths: list[Path],
    *,
    allow_actual: bool = False,
    now: datetime | None = None,
    max_age_seconds: int = 0,
) -> SequenceReport:
    sequence = SequenceReport()
    seen: set[MessageKey] = set()
    evaluation_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    for position, path in enumerate(paths, start=1):
        record_errors: list[str] = []
        try:
            data = path.read_bytes()
        except OSError as exc:
            sequence.errors.append(f"message[{position}] {path}: {exc}")
            continue
        if len(data) > MAX_XML_BYTES:
            sequence.errors.append(f"message[{position}] {path}: input exceeds size limit")
            continue

        structural = validate_capcp(path, allow_actual=allow_actual)
        record_errors.extend(structural.errors)
        if record_errors:
            sequence.errors.extend(f"message[{position}] {path.name}: {error}" for error in record_errors)
            sequence.records.append(
                {
                    "position": position,
                    "file": path.name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "accepted": False,
                    "errors": record_errors,
                }
            )
            continue

        root = ET.fromstring(data)
        key: MessageKey = (
            str(structural.fields["sender"]),
            str(structural.fields["identifier"]),
            str(structural.fields["sent"]),
        )
        msg_type = str(structural.fields["msg_type"])
        status = str(structural.fields["status"])
        scope = str(structural.fields["scope"])
        references, reference_errors = _parse_references(_text(root, "references"))
        record_errors.extend(reference_errors)

        if key in seen:
            record_errors.append("duplicate message key detected")

        if max_age_seconds:
            sent_at = _parse_time(key[2])
            if sent_at is None:
                record_errors.append("sent time cannot be evaluated for freshness")
            else:
                age = (evaluation_now - sent_at).total_seconds()
                if age < -300:
                    record_errors.append("message sent time is more than five minutes in the future")
                elif age > max_age_seconds:
                    record_errors.append(
                        f"message exceeds freshness limit ({int(age)}s > {max_age_seconds}s)"
                    )

        if msg_type in {"Update", "Cancel"} and not references:
            record_errors.append(f"{msg_type} requires at least one CAP reference")

        for reference in references:
            state = sequence.active.get(reference)
            if state is None:
                record_errors.append(
                    "reference does not identify a previously accepted message: "
                    + ",".join(reference)
                )
            elif state != "active":
                record_errors.append(
                    f"reference is not active ({state}): " + ",".join(reference)
                )
            if reference[0] != key[0]:
                record_errors.append("cross-sender Update/Cancel reference is not accepted")

        accepted = not record_errors
        if accepted:
            seen.add(key)
            if msg_type == "Alert":
                sequence.active[key] = "active"
            elif msg_type == "Update":
                for reference in references:
                    sequence.active[reference] = "superseded"
                sequence.active[key] = "active"
            elif msg_type == "Cancel":
                for reference in references:
                    sequence.active[reference] = "cancelled"
                sequence.active[key] = "terminal-cancel"

        sequence.records.append(
            {
                "position": position,
                "file": path.name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "accepted": accepted,
                "sender": key[0],
                "identifier": key[1],
                "sent": key[2],
                "status": status,
                "msg_type": msg_type,
                "scope": scope,
                "references": [
                    {"sender": ref[0], "identifier": ref[1], "sent": ref[2]}
                    for ref in references
                ],
                "errors": record_errors,
            }
        )
        sequence.errors.extend(
            f"message[{position}] {path.name}: {error}" for error in record_errors
        )

    return sequence

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml_files", nargs="+", type=Path)
    parser.add_argument("--allow-actual", action="store_true")
    parser.add_argument(
        "--max-age-seconds",
        type=int,
        default=0,
        help="optional freshness limit; zero disables wall-clock freshness checks",
    )
    parser.add_argument(
        "--now",
        help="fixed ISO-8601 evaluation time for reproducible offline testing",
    )
    args = parser.parse_args()
    if args.max_age_seconds < 0:
        parser.error("--max-age-seconds cannot be negative")
    evaluation_time = None
    if args.now:
        evaluation_time = _parse_time(args.now)
        if evaluation_time is None:
            parser.error("--now must be an ISO-8601 time with an explicit offset")
    report = validate_sequence(
        args.xml_files,
        allow_actual=args.allow_actual,
        now=evaluation_time,
        max_age_seconds=args.max_age_seconds,
    )
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.compatible else 1

if __name__ == "__main__":
    sys.exit(main())
