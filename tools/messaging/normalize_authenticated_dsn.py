#!/usr/bin/env python3
"""Normalize an authenticated RFC delivery-status notification offline.

The normalizer verifies a restricted evidence manifest and raw-message SHA-256,
parses only the machine-readable message/delivery-status part, hashes recipient
addresses, classifies bounded delivery outcomes, and emits minimized delivery
events. It does not retain raw recipients, diagnostics, message content, or
credentials; contact a provider; poll a mailbox; expose a listener; or send mail.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from datetime import datetime, timezone
from email import policy
from email.message import Message
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import outbound_mail_delivery_events as delivery_events


MANIFEST_CONTRACT = "wwcx.authenticated-dsn-evidence.v1"
OUTPUT_CONTRACT = "wwcx.authenticated-dsn-normalization.v1"
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,63}$")
CONTROL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,159}$")
STATUS_RE = re.compile(r"^([245])\.([0-9])\.([0-9]{1,3})$")
ADDRESS_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+$")


class DsnNormalizationError(RuntimeError):
    """Raised when DSN evidence is malformed, unverified, or unsupported."""


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DsnNormalizationError(f"unable to read DSN manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise DsnNormalizationError("DSN manifest must be a JSON object")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise DsnNormalizationError(
            f"{label} keys invalid; missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )


def validate_manifest(value: dict[str, Any]) -> dict[str, Any]:
    _exact_keys(
        value,
        {
            "contract",
            "captured_at",
            "source_authentication",
            "source_verified",
            "mailbox_identity_sha256",
            "evidence_sha256",
            "provider_profile",
            "provider_message_id_sha256",
            "control_id",
            "raw_message_restricted",
            "credentials_included",
            "message_content_committed",
        },
        "DSN manifest",
    )
    if value["contract"] != MANIFEST_CONTRACT:
        raise DsnNormalizationError("unsupported DSN manifest contract")
    if value["source_authentication"] != "authenticated_mailbox_dsn":
        raise DsnNormalizationError("DSN source authentication is unsupported")
    if value["source_verified"] is not True:
        raise DsnNormalizationError("DSN source is not verified")
    if value["raw_message_restricted"] is not True:
        raise DsnNormalizationError("raw DSN evidence is not marked restricted")
    if value["credentials_included"] is not False:
        raise DsnNormalizationError("DSN evidence includes credentials")
    if value["message_content_committed"] is not False:
        raise DsnNormalizationError("DSN evidence permits committed message content")
    for key in (
        "mailbox_identity_sha256",
        "evidence_sha256",
        "provider_message_id_sha256",
    ):
        if not isinstance(value[key], str) or not HEX64_RE.fullmatch(value[key]):
            raise DsnNormalizationError(f"manifest {key} is invalid")
    if not isinstance(value["provider_profile"], str) or not PROFILE_RE.fullmatch(
        value["provider_profile"]
    ):
        raise DsnNormalizationError("manifest provider_profile is invalid")
    if not isinstance(value["control_id"], str) or not CONTROL_ID_RE.fullmatch(
        value["control_id"]
    ):
        raise DsnNormalizationError("manifest control_id is invalid")
    _parse_iso_timestamp(value["captured_at"], "captured_at")
    return value


def _parse_iso_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise DsnNormalizationError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DsnNormalizationError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise DsnNormalizationError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _message_timestamp(message: Message, block: Message, fallback: str) -> str:
    for candidate in (
        block.get("Last-Attempt-Date"),
        block.get("Arrival-Date"),
        message.get("Date"),
    ):
        if not candidate:
            continue
        try:
            parsed = parsedate_to_datetime(str(candidate))
        except (TypeError, ValueError, OverflowError):
            continue
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return _format_timestamp(parsed)
    return _format_timestamp(_parse_iso_timestamp(fallback, "captured_at"))


def _recipient(value: Any) -> str:
    if not isinstance(value, str) or ";" not in value:
        raise DsnNormalizationError("Final-Recipient is absent or malformed")
    address_type, raw_address = value.split(";", 1)
    if address_type.strip().casefold() not in {"rfc822", "utf-8"}:
        raise DsnNormalizationError("Final-Recipient address type is unsupported")
    address = raw_address.strip().casefold()
    if not ADDRESS_RE.fullmatch(address):
        raise DsnNormalizationError("Final-Recipient address is invalid")
    return address


def _classify_diagnostic(event_type: str, status_match: re.Match[str], diagnostic: str) -> str:
    subject = int(status_match.group(2))
    lower = diagnostic.casefold()
    if event_type == "delivered":
        return "none"
    if subject in {1, 2}:
        return "mailbox_unavailable"
    if subject == 4:
        return "domain_unavailable"
    if event_type == "permanent_bounce" and subject == 7:
        return "policy_rejection"
    if event_type == "transient_bounce":
        if any(token in lower for token in ("rate", "throttl", "too many", "try again")):
            return "rate_limited"
        if subject == 3:
            return "provider_unavailable"
    return "unknown"


def _event_type(action: str, status_match: re.Match[str]) -> str:
    action = action.casefold()
    major = status_match.group(1)
    if action in {"delivered", "relayed", "expanded"} and major == "2":
        return "delivered"
    if action == "delayed" and major == "4":
        return "transient_bounce"
    if action == "failed" and major == "4":
        return "transient_bounce"
    if action == "failed" and major == "5":
        return "permanent_bounce"
    raise DsnNormalizationError(
        f"unsupported DSN action/status combination: {action}/{status_match.group(0)}"
    )


def _delivery_status_blocks(message: Message) -> list[Message]:
    if message.get_content_type() != "multipart/report":
        raise DsnNormalizationError("DSN must be multipart/report")
    report_type = str(message.get_param("report-type", header="content-type") or "")
    if report_type.casefold() != "delivery-status":
        raise DsnNormalizationError("multipart report-type must be delivery-status")
    parts = [
        part
        for part in message.walk()
        if part.get_content_type() in {"message/delivery-status", "message/global-delivery-status"}
    ]
    if len(parts) != 1:
        raise DsnNormalizationError("DSN must contain exactly one delivery-status part")
    payload = parts[0].get_payload()
    if not isinstance(payload, list) or not payload:
        raise DsnNormalizationError("delivery-status part has no machine-readable blocks")
    blocks = [item for item in payload if isinstance(item, Message)]
    recipient_blocks = [item for item in blocks if item.get("Final-Recipient")]
    if not recipient_blocks:
        raise DsnNormalizationError("delivery-status part has no recipient blocks")
    return recipient_blocks


def normalize(raw_message: bytes, manifest: dict[str, Any]) -> dict[str, Any]:
    evidence = validate_manifest(manifest)
    digest = hashlib.sha256(raw_message).hexdigest()
    if digest != evidence["evidence_sha256"]:
        raise DsnNormalizationError("raw DSN SHA-256 does not match the manifest")
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw_message)
    except Exception as exc:
        raise DsnNormalizationError(f"unable to parse DSN MIME message: {exc}") from exc

    events: list[dict[str, Any]] = []
    for index, block in enumerate(_delivery_status_blocks(message), start=1):
        address = _recipient(block.get("Final-Recipient"))
        recipient_hash = hashlib.sha256(address.encode("utf-8")).hexdigest()
        action = str(block.get("Action") or "").strip().casefold()
        status = str(block.get("Status") or "").strip()
        status_match = STATUS_RE.fullmatch(status)
        if not action or status_match is None:
            raise DsnNormalizationError("recipient block lacks a supported Action or Status")
        event_type = _event_type(action, status_match)
        diagnostic = str(block.get("Diagnostic-Code") or "")
        diagnostic_class = _classify_diagnostic(event_type, status_match, diagnostic)
        event_id_material = (
            f"{digest}:{recipient_hash}:{action}:{status}:{index}".encode("utf-8")
        )
        event_id = "dsn:" + hashlib.sha256(event_id_material).hexdigest()[:40]
        event = {
            "contract": delivery_events.CONTRACT,
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": _message_timestamp(message, block, evidence["captured_at"]),
            "provider_profile": evidence["provider_profile"],
            "provider_message_id_sha256": evidence["provider_message_id_sha256"],
            "control_id": evidence["control_id"],
            "recipient_sha256": recipient_hash,
            "source_evidence_sha256": digest,
            "source_authentication": "authenticated_mailbox_dsn",
            "source_verified": True,
            "diagnostic_class": diagnostic_class,
            "retryable": event_type == "transient_bounce",
            "raw_recipient_stored": False,
            "raw_payload_stored": False,
            "message_content_stored": False,
        }
        delivery_events.validate_event(event)
        events.append(event)

    return {
        "contract": OUTPUT_CONTRACT,
        "source_evidence_sha256": digest,
        "source_authentication": "authenticated_mailbox_dsn",
        "source_verified": True,
        "provider_profile": evidence["provider_profile"],
        "control_id": evidence["control_id"],
        "event_count": len(events),
        "events": events,
        "raw_recipient_stored": False,
        "raw_diagnostic_stored": False,
        "raw_payload_stored": False,
        "message_content_stored": False,
        "credentials_inspected": False,
        "network_access_performed": False,
        "mailbox_access_performed": False,
        "message_sent": False,
    }


def _inside_repo(path: pathlib.Path) -> bool:
    resolved = path.resolve()
    root = ROOT.resolve()
    return resolved == root or root in resolved.parents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", type=pathlib.Path, required=True)
    parser.add_argument("--manifest", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for label, path in (("DSN", args.dsn), ("manifest", args.manifest)):
        if _inside_repo(path):
            print(f"refusing {label} evidence inside the Git working tree", file=sys.stderr)
            return 2
    if args.output is not None and _inside_repo(args.output):
        print("refusing normalized DSN output inside the Git working tree", file=sys.stderr)
        return 2
    try:
        raw_message = args.dsn.read_bytes()
        report = normalize(raw_message, load_json(args.manifest))
    except (OSError, DsnNormalizationError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    rendered = json.dumps(
        report,
        indent=2 if args.pretty else None,
        sort_keys=True,
        separators=None if args.pretty else (",", ":"),
    ) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
