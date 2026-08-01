#!/usr/bin/env python3
"""Fail-closed adapters for already-sanitized telephony event records.

The adapters normalize bounded CDR-style and SIP-event mappings into CallEvent
objects. They deliberately perform no file, database, network, credential,
service-control, PBX, carrier, route, or configuration access.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Iterable, Mapping

from telephony_platform import CallEvent

SCHEMA_VERSION = "1.0"
MAX_DURATION_SECONDS = 604800

DIRECTION_ALIASES = {
    "in": "inbound",
    "inbound": "inbound",
    "incoming": "inbound",
    "out": "outbound",
    "outbound": "outbound",
    "outgoing": "outbound",
    "internal": "internal",
    "local": "internal",
    "unknown": "unknown",
}

DISPOSITION_ALIASES = {
    "answer": "answered",
    "answered": "answered",
    "complete": "completed",
    "completed": "completed",
    "busy": "busy",
    "no_answer": "no_answer",
    "noanswer": "no_answer",
    "failed": "failed",
    "failure": "failed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "declined": "rejected",
    "rejected": "rejected",
    "progress": "progress",
    "unknown": "unknown",
}

CDR_ALLOWED_FIELDS = {
    "schema_version",
    "source_record_id",
    "observed_at",
    "direction",
    "call_direction",
    "disposition",
    "status",
    "sip_code",
    "response_code",
    "carrier_id",
    "provider_id",
    "destination_country",
    "country_code",
    "duration_seconds",
    "billsec",
}

SIP_EVENT_ALLOWED_FIELDS = {
    "schema_version",
    "source_record_id",
    "observed_at",
    "direction",
    "call_direction",
    "disposition",
    "final_disposition",
    "sip_code",
    "response_code",
    "carrier_id",
    "provider_id",
    "destination_country",
    "country_code",
    "duration_seconds",
    "event_type",
}

PROHIBITED_FIELDS = {
    "accountcode",
    "address",
    "ani",
    "auth",
    "authorization",
    "body",
    "call_id",
    "called",
    "called_number",
    "callee",
    "caller",
    "caller_id",
    "callerid",
    "calling",
    "calling_number",
    "channel",
    "clid",
    "contact",
    "credential",
    "dnis",
    "dst",
    "email",
    "from",
    "header",
    "headers",
    "ip",
    "linkedid",
    "local_address",
    "media",
    "message",
    "name",
    "number",
    "password",
    "phone",
    "recording",
    "remote_address",
    "sdp",
    "secret",
    "sip_uri",
    "src",
    "token",
    "to",
    "uniqueid",
    "uri",
    "userfield",
}

SAFE_ID_RE = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
EVENT_TYPE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
COUNTRY_RE = re.compile(r"^(?:[A-Z]{2}|unknown)$")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SIP_URI_RE = re.compile(r"\b(?:sip|sips|tel):", re.IGNORECASE)
IPV4_RE = re.compile(r"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])")
PHONE_RE = re.compile(r"(?<![A-Za-z0-9])\+?[0-9][0-9 ()-]{6,}[0-9](?![A-Za-z0-9])")
LONG_DIGIT_RE = re.compile(r"[0-9]{7,}")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class SanitizedAdapterError(ValueError):
    """Raised when a record is outside the privacy-minimized adapter contract."""


def _normalized_key(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _normalized_token(value: Any) -> str:
    return _normalized_key(value)


def _first(record: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in record and record[key] is not None:
            return record[key]
    return default


def _validate_shape(record: Mapping[str, Any], allowed_fields: set[str]) -> None:
    if not isinstance(record, Mapping):
        raise SanitizedAdapterError("record must be a mapping")

    normalized_keys: dict[str, str] = {}
    for original_key, value in record.items():
        if not isinstance(original_key, str):
            raise SanitizedAdapterError("record keys must be strings")
        key = _normalized_key(original_key)
        if key in normalized_keys:
            raise SanitizedAdapterError("record contains duplicate normalized field: %s" % key)
        normalized_keys[key] = original_key
        if key in PROHIBITED_FIELDS:
            raise SanitizedAdapterError("record contains prohibited sensitive field: %s" % original_key)
        if key not in allowed_fields:
            raise SanitizedAdapterError("record contains unsupported field: %s" % original_key)
        if isinstance(value, (Mapping, list, tuple, set)):
            raise SanitizedAdapterError("record field must be scalar: %s" % original_key)
        if isinstance(value, str):
            if CONTROL_RE.search(value):
                raise SanitizedAdapterError("record field contains control characters: %s" % original_key)
            if EMAIL_RE.search(value) or SIP_URI_RE.search(value) or IPV4_RE.search(value):
                raise SanitizedAdapterError("record field contains prohibited address or URI data: %s" % original_key)


def _validate_schema_version(record: Mapping[str, Any]) -> None:
    version = str(record.get("schema_version", SCHEMA_VERSION)).strip()
    if version != SCHEMA_VERSION:
        raise SanitizedAdapterError("unsupported schema_version")


def _opaque_id(value: Any, field_name: str) -> str:
    token = str(value or "").strip().lower()
    if not SAFE_ID_RE.fullmatch(token):
        raise SanitizedAdapterError("%s must be an opaque lowercase identifier" % field_name)
    if LONG_DIGIT_RE.search(token) or PHONE_RE.search(token):
        raise SanitizedAdapterError("%s must not contain a telephone or account number" % field_name)
    return token


def _timestamp(value: Any) -> str:
    text = str(value or "").strip()
    if not text.endswith("Z"):
        raise SanitizedAdapterError("observed_at must be an RFC 3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise SanitizedAdapterError("observed_at must be an RFC 3339 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SanitizedAdapterError("observed_at must include UTC timezone information")
    return parsed.isoformat().replace("+00:00", "Z")


def _direction(value: Any) -> str:
    token = _normalized_token(value if value is not None else "unknown")
    if token not in DIRECTION_ALIASES:
        raise SanitizedAdapterError("unsupported call direction")
    return DIRECTION_ALIASES[token]


def _disposition(value: Any) -> str:
    token = _normalized_token(value if value is not None else "unknown")
    if token not in DISPOSITION_ALIASES:
        raise SanitizedAdapterError("unsupported call disposition")
    return DISPOSITION_ALIASES[token]


def _sip_code(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise SanitizedAdapterError("sip_code must be an integer")
    try:
        code = int(value)
    except (TypeError, ValueError) as exc:
        raise SanitizedAdapterError("sip_code must be an integer") from exc
    if not 100 <= code <= 699:
        raise SanitizedAdapterError("sip_code must be between 100 and 699")
    return code


def _duration(value: Any) -> int:
    if isinstance(value, bool):
        raise SanitizedAdapterError("duration_seconds must be an integer")
    try:
        duration = int(value if value is not None else 0)
    except (TypeError, ValueError) as exc:
        raise SanitizedAdapterError("duration_seconds must be an integer") from exc
    if duration < 0 or duration > MAX_DURATION_SECONDS:
        raise SanitizedAdapterError("duration_seconds is outside the accepted range")
    return duration


def _country(value: Any) -> str | None:
    if value is None or value == "":
        return None
    country = str(value).strip().upper()
    if country == "UNKNOWN":
        country = "unknown"
    if not COUNTRY_RE.fullmatch(country):
        raise SanitizedAdapterError("destination_country must be a two-letter code or unknown")
    return country


def _optional_opaque_id(value: Any, field_name: str) -> str | None:
    if value is None or value == "":
        return None
    return _opaque_id(value, field_name)


def _derive_sip_disposition(code: int | None) -> str:
    if code is None:
        return "unknown"
    if code < 200:
        return "progress"
    if code < 300:
        return "completed"
    return "failed"


def adapt_sanitized_cdr(record: Mapping[str, Any]) -> CallEvent:
    """Normalize one already-sanitized CDR mapping into a CallEvent."""
    _validate_shape(record, CDR_ALLOWED_FIELDS)
    _validate_schema_version(record)

    source_record_id = _opaque_id(record.get("source_record_id"), "source_record_id")
    observed_at = _timestamp(record.get("observed_at"))
    direction = _direction(_first(record, "direction", "call_direction", default="unknown"))
    disposition = _disposition(_first(record, "disposition", "status", default="unknown"))
    sip_code = _sip_code(_first(record, "sip_code", "response_code"))
    carrier_id = _optional_opaque_id(_first(record, "carrier_id", "provider_id"), "carrier_id")
    destination_country = _country(_first(record, "destination_country", "country_code"))
    duration_seconds = _duration(_first(record, "duration_seconds", "billsec", default=0))

    return CallEvent(
        direction=direction,
        disposition=disposition,
        sip_code=sip_code,
        carrier_id=carrier_id,
        destination_country=destination_country,
        duration_seconds=duration_seconds,
        metadata={
            "adapter": "sanitized_cdr",
            "schema_version": SCHEMA_VERSION,
            "source_record_id": source_record_id,
            "observed_at": observed_at,
        },
    )


def adapt_sanitized_sip_event(record: Mapping[str, Any]) -> CallEvent:
    """Normalize one already-sanitized SIP event mapping into a CallEvent."""
    _validate_shape(record, SIP_EVENT_ALLOWED_FIELDS)
    _validate_schema_version(record)

    source_record_id = _opaque_id(record.get("source_record_id"), "source_record_id")
    observed_at = _timestamp(record.get("observed_at"))
    event_type = str(record.get("event_type", "")).strip().lower()
    if not EVENT_TYPE_RE.fullmatch(event_type):
        raise SanitizedAdapterError("event_type must be a lowercase operational slug")

    direction = _direction(_first(record, "direction", "call_direction", default="unknown"))
    sip_code = _sip_code(_first(record, "sip_code", "response_code"))
    raw_disposition = _first(record, "disposition", "final_disposition")
    disposition = _disposition(raw_disposition) if raw_disposition is not None else _derive_sip_disposition(sip_code)
    carrier_id = _optional_opaque_id(_first(record, "carrier_id", "provider_id"), "carrier_id")
    destination_country = _country(_first(record, "destination_country", "country_code"))
    duration_seconds = _duration(record.get("duration_seconds", 0))

    return CallEvent(
        direction=direction,
        disposition=disposition,
        sip_code=sip_code,
        carrier_id=carrier_id,
        destination_country=destination_country,
        duration_seconds=duration_seconds,
        metadata={
            "adapter": "sanitized_sip_event",
            "schema_version": SCHEMA_VERSION,
            "source_record_id": source_record_id,
            "observed_at": observed_at,
            "event_type": event_type,
        },
    )


def adapt_sanitized_cdr_rows(records: Iterable[Mapping[str, Any]]) -> list[CallEvent]:
    """Adapt a CDR batch and fail the entire batch on the first invalid record."""
    events: list[CallEvent] = []
    for index, record in enumerate(records):
        try:
            events.append(adapt_sanitized_cdr(record))
        except SanitizedAdapterError as exc:
            raise SanitizedAdapterError("CDR record %d rejected: %s" % (index, exc)) from exc
    return events


def adapt_sanitized_sip_events(records: Iterable[Mapping[str, Any]]) -> list[CallEvent]:
    """Adapt a SIP-event batch and fail the entire batch on the first invalid record."""
    events: list[CallEvent] = []
    for index, record in enumerate(records):
        try:
            events.append(adapt_sanitized_sip_event(record))
        except SanitizedAdapterError as exc:
            raise SanitizedAdapterError("SIP event %d rejected: %s" % (index, exc)) from exc
    return events
