#!/usr/bin/env python3
"""Validate captured aggregate telephony analytics payloads for contract and privacy."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SIP_URI_RE = re.compile(r"(?i)\bsips?:[^\s]+")
LONG_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])\+?[0-9][0-9 ()-]{6,}[0-9](?![A-Za-z0-9])")
IPV4_RE = re.compile(r"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])")
ISO_DATE_RE = re.compile(r"\b[0-9]{4}-[0-9]{2}-[0-9]{2}(?:T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)?\b")
PROHIBITED_KEYS = {
    "caller", "caller_id", "callerid", "callee", "called_number", "calling_number",
    "did", "phone", "phone_number", "telephone_number", "extension", "account",
    "account_id", "account_number", "username", "password", "secret", "token",
    "api_key", "credential", "credentials", "sip_uri", "email", "email_address",
    "message_body", "audio", "recording", "recording_path", "source_ip", "destination_ip",
}


def load_object(root: Path, name: str, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads((root / name).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"{name}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{name}: root must be an object")
        return {}
    return value


def walk(value: Any, errors: list[str], location: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in PROHIBITED_KEYS:
                errors.append(f"{location}: prohibited key {key}")
            walk(child, errors, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk(child, errors, f"{location}[{index}]")
    elif isinstance(value, str):
        if EMAIL_RE.search(value):
            errors.append(f"{location}: email-like value")
        if SIP_URI_RE.search(value):
            errors.append(f"{location}: SIP URI-like value")
        if IPV4_RE.search(value) and value != "127.0.0.1":
            errors.append(f"{location}: IP-like value")
        if LONG_NUMBER_RE.search(ISO_DATE_RE.sub("", value)):
            errors.append(f"{location}: long number-like value")


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    healthz = load_object(root, "healthz.json", errors)
    require(healthz.get("status") == "ok", "healthz.status must be ok", errors)
    require(healthz.get("mode") == "read_only", "healthz.mode must be read_only", errors)

    health = load_object(root, "platform-health.json", errors)
    score = health.get("score")
    require(isinstance(score, int) and 0 <= score <= 100, "health score must be 0..100", errors)
    require(health.get("overall_status") in {"healthy", "degraded", "critical"},
            "health overall_status is invalid", errors)
    require(isinstance(health.get("components"), dict), "health components must be an object", errors)

    calls = load_object(root, "calls-summary.json", errors)
    for key in ("calls_total", "calls_answered", "answer_rate_percent", "duration_seconds_total", "duration_seconds_average"):
        require(isinstance(calls.get(key), (int, float)), f"calls summary missing numeric {key}", errors)
    for key in ("directions", "dispositions", "carriers", "destination_countries", "sip_codes", "failure_classes"):
        require(isinstance(calls.get(key), dict), f"calls summary missing object {key}", errors)

    interconnects = load_object(root, "interconnects-summary.json", errors)
    require(isinstance(interconnects.get("interconnects_total"), int),
            "interconnects_total must be an integer", errors)
    require(isinstance(interconnects.get("states"), dict), "interconnect states must be an object", errors)
    require(isinstance(interconnects.get("attention_required"), int),
            "attention_required must be an integer", errors)

    for filename in ("healthz.json", "platform-health.json", "calls-summary.json", "interconnects-summary.json", "post-response.json"):
        path = root / filename
        if not path.is_file():
            continue
        try:
            walk(json.loads(path.read_text(encoding="utf-8")), errors, filename)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{filename}: privacy scan failed: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_dir", type=Path)
    args = parser.parse_args()
    errors = validate(args.evidence_dir)
    output = args.evidence_dir / "payload-validation.txt"
    if errors:
        output.write_text("\n".join(errors) + "\n", encoding="utf-8")
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    output.write_text("payload_validation=passed\nprivacy_scan=passed\n", encoding="utf-8")
    print("payload_validation=passed")
    print("privacy_scan=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
