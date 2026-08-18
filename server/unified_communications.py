#!/usr/bin/env python3
"""Pure, channel-neutral WW.CX Communications metadata helpers.

This module intentionally performs no provider, network, filesystem, telephony,
mail-delivery, or messaging mutation. Native channel records remain authoritative.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Iterable


CONTRACT = "wwcx.communications-event.v1"
CHANNELS = {"email", "sms", "mms", "voice", "sip", "nntp", "relay", "system"}
DIRECTIONS = {"inbound", "outbound", "internal"}
STATES = {
    "observed",
    "summarized",
    "drafted",
    "reviewed",
    "approved",
    "queued",
    "submitted",
    "delivered",
    "failed",
    "suppressed",
    "quarantined",
    "closed",
}
SEARCH_FIELDS = {
    "communications_event_id",
    "conversation_id",
    "thread_id",
    "case_id",
    "control_id",
    "channel",
    "direction",
    "sender_identity_ref",
    "recipient_identity_refs",
    "subject_or_summary",
    "status",
    "security.state",
    "native_record.record_id",
    "native_record.source",
    "native_record.provider",
}
FORBIDDEN_EMBEDDED_KEYS = {
    "body",
    "raw_body",
    "raw_message",
    "audio",
    "audio_bytes",
    "attachment_bytes",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "token",
}


class CommunicationsContractError(ValueError):
    pass


def _walk_forbidden(value: Any, path: str = "event") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in FORBIDDEN_EMBEDDED_KEYS:
                raise CommunicationsContractError(f"embedded raw/private field forbidden: {path}.{key}")
            _walk_forbidden(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_forbidden(child, f"{path}[{index}]")


def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise CommunicationsContractError("timestamp_utc must be a non-empty string")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CommunicationsContractError("timestamp_utc must be ISO-8601") from exc
    if timestamp.tzinfo is None:
        raise CommunicationsContractError("timestamp_utc must be timezone-aware")
    return timestamp.astimezone(timezone.utc)


def validate_event(event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise CommunicationsContractError("event must be an object")
    _walk_forbidden(event)
    required = {
        "contract",
        "communications_event_id",
        "channel",
        "direction",
        "timestamp_utc",
        "sender_identity_ref",
        "recipient_identity_refs",
        "native_record",
        "status",
        "security",
        "provenance",
        "audit_refs",
    }
    missing = sorted(required - set(event))
    if missing:
        raise CommunicationsContractError(f"missing event fields: {', '.join(missing)}")
    if event["contract"] != CONTRACT:
        raise CommunicationsContractError("unsupported communications event contract")
    if event["channel"] not in CHANNELS:
        raise CommunicationsContractError("unsupported channel")
    if event["direction"] not in DIRECTIONS:
        raise CommunicationsContractError("unsupported direction")
    if event["status"] not in STATES:
        raise CommunicationsContractError("unsupported status")
    _parse_timestamp(event["timestamp_utc"])
    native = event["native_record"]
    if not isinstance(native, dict) or not native.get("record_id") or not native.get("source"):
        raise CommunicationsContractError("native_record must reference an authoritative source record")
    provenance = event["provenance"]
    if not isinstance(provenance, dict):
        raise CommunicationsContractError("provenance must be an object")
    if provenance.get("source_channel") != event["channel"]:
        raise CommunicationsContractError("provenance source_channel must match event channel")
    if provenance.get("authoritative_native_record") is not True:
        raise CommunicationsContractError("native record must remain authoritative")
    security = event["security"]
    if not isinstance(security, dict) or security.get("quarantine_release_authorized") is not False:
        raise CommunicationsContractError("unified event layer cannot authorize quarantine release")
    if not isinstance(event["recipient_identity_refs"], list):
        raise CommunicationsContractError("recipient_identity_refs must be a list")
    if not isinstance(event["audit_refs"], list):
        raise CommunicationsContractError("audit_refs must be a list")
    return deepcopy(event)


def sort_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    validated = [validate_event(event) for event in events]
    return sorted(
        validated,
        key=lambda item: (_parse_timestamp(item["timestamp_utc"]), item["communications_event_id"]),
    )


def _get_field(event: dict[str, Any], field: str) -> Any:
    value: Any = event
    for part in field.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def search_events(
    events: Iterable[dict[str, Any]],
    query: str,
    *,
    fields: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Search bounded metadata only; raw content is neither accepted nor indexed."""
    needle = str(query).casefold().strip()
    selected = set(fields or SEARCH_FIELDS)
    unknown = selected - SEARCH_FIELDS
    if unknown:
        raise CommunicationsContractError(f"unapproved search fields: {', '.join(sorted(unknown))}")
    if not needle:
        return sort_events(events)
    matches: list[dict[str, Any]] = []
    for event in sort_events(events):
        for field in selected:
            value = _get_field(event, field)
            values = value if isinstance(value, list) else [value]
            if any(needle in str(item).casefold() for item in values if item is not None):
                matches.append(event)
                break
    return matches


def resolve_identity_links(registry: dict[str, Any], identity_ref: str) -> list[dict[str, Any]]:
    """Return only explicitly evidenced identity links; never infer by similar names."""
    policy = registry.get("correlation_policy", {})
    if policy.get("explicit_evidence_required") is not True:
        raise CommunicationsContractError("identity registry must require explicit evidence")
    results: list[dict[str, Any]] = []
    for link in registry.get("links", []):
        if not isinstance(link, dict):
            continue
        endpoints = link.get("identity_refs", [])
        evidence = link.get("evidence_refs", [])
        if identity_ref in endpoints and isinstance(evidence, list) and evidence:
            results.append(deepcopy(link))
    return results


def correlate_conversation(events: Iterable[dict[str, Any]], conversation_id: str) -> list[dict[str, Any]]:
    return sort_events(
        event for event in events if event.get("conversation_id") == conversation_id
    )


def sanitize_derived_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop permission-like data from retrieved/untrusted material before derivation."""
    forbidden = {
        "scopes",
        "permissions",
        "requested_scopes",
        "tool_authority",
        "authorize",
        "authorization",
    }
    clean = {key: deepcopy(value) for key, value in payload.items() if key.lower() not in forbidden}
    _walk_forbidden(clean, "derived")
    return clean
