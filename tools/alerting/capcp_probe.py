#!/usr/bin/env python3
"""Read-only CAP 1.2 / CAP-CP compatibility probe.

This tool validates a bounded XML file and emits a sanitized JSON report. It is
intentionally a consumer-side laboratory probe. By default it rejects Actual
alerts so it cannot be mistaken for an operational public-alert originator.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
CAP = f"{{{CAP_NS}}}"
MAX_XML_BYTES = 2 * 1024 * 1024
CAPCP_CODE_PREFIX = "profile:CAP-CP:"
CAPCP_EVENT_PREFIX = "profile:CAP-CP:Event:"
CAPCP_LOCATION_PREFIX = "profile:CAP-CP:Location:"

STATUS_VALUES = {"Actual", "Exercise", "System", "Test", "Draft"}
MSG_TYPE_VALUES = {"Alert", "Update", "Cancel", "Ack", "Error"}
SCOPE_VALUES = {"Public", "Restricted", "Private"}
URGENCY_VALUES = {"Immediate", "Expected", "Future", "Past", "Unknown"}
SEVERITY_VALUES = {"Extreme", "Severe", "Moderate", "Minor", "Unknown"}
CERTAINTY_VALUES = {"Observed", "Likely", "Possible", "Unlikely", "Unknown"}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fields: dict[str, object] = field(default_factory=dict)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    @property
    def compatible(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, object]:
        return {
            "compatible": self.compatible,
            "profile": "CAP 1.2 / CAP-CP consumer compatibility baseline",
            "operating_mode": "read-only test laboratory",
            "fields": self.fields,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _text(parent: ET.Element, name: str) -> str:
    child = parent.find(CAP + name)
    return (child.text or "").strip() if child is not None else ""


def _texts(parent: ET.Element, name: str) -> list[str]:
    values: list[str] = []
    for child in parent.findall(CAP + name):
        value = (child.text or "").strip()
        if value:
            values.append(value)
    return values


def _require(report: Report, parent: ET.Element, name: str, context: str) -> str:
    value = _text(parent, name)
    if not value:
        report.error(f"{context}: missing required <{name}> value")
    return value


def _check_enum(report: Report, value: str, allowed: set[str], field_name: str) -> None:
    if value and value not in allowed:
        report.error(f"<{field_name}> has unsupported value {value!r}")


def _check_cap_datetime(report: Report, value: str, field_name: str) -> None:
    if not value:
        return
    if value.endswith("Z"):
        report.error(f"<{field_name}> uses Z; CAP 1.2 requires an explicit numeric offset")
        return
    if not re.search(r"[+-]\d{2}:\d{2}$", value):
        report.error(f"<{field_name}> must include a numeric timezone offset")
        return
    try:
        datetime.fromisoformat(value)
    except ValueError:
        report.error(f"<{field_name}> is not a valid ISO 8601 date-time")


def _pairs(parent: ET.Element, pair_name: str) -> Iterable[tuple[str, str]]:
    for pair in parent.findall(CAP + pair_name):
        yield _text(pair, "valueName"), _text(pair, "value")


def validate_capcp(path: Path, *, allow_actual: bool = False) -> Report:
    report = Report()
    data = path.read_bytes()
    report.fields["input_bytes"] = len(data)

    if len(data) > MAX_XML_BYTES:
        report.error(f"input exceeds bounded size limit of {MAX_XML_BYTES} bytes")
        return report

    upper = data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        report.error("DTD and entity declarations are prohibited")
        return report

    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        report.error(f"XML parse error: {exc}")
        return report

    if root.tag != CAP + "alert":
        report.error(f"root element must be CAP 1.2 <alert> in namespace {CAP_NS}")
        return report

    identifier = _require(report, root, "identifier", "alert")
    sender = _require(report, root, "sender", "alert")
    sent = _require(report, root, "sent", "alert")
    status = _require(report, root, "status", "alert")
    msg_type = _require(report, root, "msgType", "alert")
    scope = _require(report, root, "scope", "alert")

    _check_cap_datetime(report, sent, "sent")
    _check_enum(report, status, STATUS_VALUES, "status")
    _check_enum(report, msg_type, MSG_TYPE_VALUES, "msgType")
    _check_enum(report, scope, SCOPE_VALUES, "scope")

    if status == "Actual" and not allow_actual:
        report.error("Actual alerts are blocked in the default laboratory safety mode")

    if scope == "Restricted" and not _text(root, "restriction"):
        report.error("Restricted scope requires <restriction>")
    if scope == "Private" and not _text(root, "addresses"):
        report.error("Private scope requires <addresses>")

    profile_codes = [value for value in _texts(root, "code") if value.startswith(CAPCP_CODE_PREFIX)]
    if not profile_codes:
        report.error("message does not identify a CAP-CP profile in <code>")

    info_blocks = root.findall(CAP + "info")
    if msg_type in {"Alert", "Update", "Cancel"} and not info_blocks:
        report.error(f"{msg_type} message requires at least one <info> block")

    event_identities: set[tuple[str, str]] = set()
    languages: list[str] = []
    area_count = 0

    for index, info in enumerate(info_blocks, start=1):
        context = f"info[{index}]"
        language = _require(report, info, "language", context)
        if language:
            languages.append(language)

        _require(report, info, "category", context)
        _require(report, info, "event", context)
        urgency = _require(report, info, "urgency", context)
        severity = _require(report, info, "severity", context)
        certainty = _require(report, info, "certainty", context)
        _check_enum(report, urgency, URGENCY_VALUES, "urgency")
        _check_enum(report, severity, SEVERITY_VALUES, "severity")
        _check_enum(report, certainty, CERTAINTY_VALUES, "certainty")

        event_pairs = [
            (name, value)
            for name, value in _pairs(info, "eventCode")
            if name.startswith(CAPCP_EVENT_PREFIX) and value
        ]
        if not event_pairs:
            report.error(f"{context}: missing CAP-CP event reference")
        event_identities.update(event_pairs)

        areas = info.findall(CAP + "area")
        if not areas:
            report.error(f"{context}: missing <area>")

        for area_index, area in enumerate(areas, start=1):
            area_count += 1
            area_context = f"{context}.area[{area_index}]"
            _require(report, area, "areaDesc", area_context)
            location_pairs = [
                (name, value)
                for name, value in _pairs(area, "geocode")
                if name.startswith(CAPCP_LOCATION_PREFIX) and value
            ]
            has_shape = bool(_texts(area, "polygon") or _texts(area, "circle"))
            if not location_pairs and not has_shape:
                report.error(
                    f"{area_context}: requires a CAP-CP location reference or CAP polygon/circle"
                )
            elif not location_pairs:
                report.warn(
                    f"{area_context}: geospatial shape present without CAP-CP location reference"
                )

    if len(event_identities) > 1:
        rendered = ", ".join(f"{name}={value}" for name, value in sorted(event_identities))
        report.error(f"CAP-CP requires one subject event type per alert; found {rendered}")

    if len(set(languages)) != len(languages):
        report.warn("duplicate <language> values appear in multiple <info> blocks")

    report.fields.update(
        {
            "identifier": identifier,
            "sender": sender,
            "sent": sent,
            "status": status,
            "msg_type": msg_type,
            "scope": scope,
            "capcp_profile_codes": profile_codes,
            "languages": languages,
            "info_blocks": len(info_blocks),
            "areas": area_count,
            "subject_event_types": [
                {"value_name": name, "value": value}
                for name, value in sorted(event_identities)
            ],
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml_file", type=Path)
    parser.add_argument(
        "--allow-actual",
        action="store_true",
        help="permit Actual messages for offline validation only",
    )
    args = parser.parse_args()

    try:
        report = validate_capcp(args.xml_file, allow_actual=args.allow_actual)
    except OSError as exc:
        print(json.dumps({"compatible": False, "errors": [str(exc)]}, indent=2))
        return 2

    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.compatible else 1


if __name__ == "__main__":
    sys.exit(main())
