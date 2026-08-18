#!/usr/bin/env python3
"""Validated Mail Room correspondence and thread-correlation metadata.

This module is deliberately provider-neutral and performs no network activity. It
normalizes explicit correlation evidence supplied by a trusted server-side intake
or operator workflow. It does not guess thread relationships from subject lines or
sender names.
"""

from __future__ import annotations

import re
from typing import Any


CONTRACT = "wwcx.mail-threading.v1"
CONTROL_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{5,127}$")
MESSAGE_ID_RE = re.compile(r"^<[^<>\r\n\s]+@[^<>\r\n\s]+>$")


class ThreadingError(ValueError):
    """Raised when supplied thread-correlation metadata is unsafe or malformed."""


def _optional_control_id(value: Any, label: str) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    normalized = str(value).strip()
    if not CONTROL_ID_RE.fullmatch(normalized):
        raise ThreadingError(f"{label} is invalid")
    return normalized


def _optional_text(value: Any, label: str, maximum: int = 512) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    normalized = str(value).strip()
    if "\r" in normalized or "\n" in normalized or len(normalized) > maximum:
        raise ThreadingError(f"{label} is invalid")
    return normalized


def _optional_message_id(value: Any, label: str) -> str | None:
    normalized = _optional_text(value, label, maximum=998)
    if normalized is None:
        return None
    if not MESSAGE_ID_RE.fullmatch(normalized):
        raise ThreadingError(f"{label} must be a canonical RFC-style Message-ID")
    return normalized


def _references(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if not isinstance(value, list):
        raise ThreadingError("references must be a list of Message-ID values")
    if len(value) > 100:
        raise ThreadingError("references exceeds the configured count limit")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        message_id = _optional_message_id(item, "references item")
        if message_id is None:
            continue
        if message_id not in seen:
            seen.add(message_id)
            normalized.append(message_id)
    return normalized


def normalize_thread_context(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ThreadingError("message payload must be an object")

    correspondence_id = _optional_control_id(
        payload.get("correspondence_id"), "correspondence_id"
    )
    thread_id = _optional_control_id(payload.get("thread_id"), "thread_id")
    source_message_id = _optional_message_id(
        payload.get("source_message_id"), "source_message_id"
    )
    in_reply_to = _optional_message_id(payload.get("in_reply_to"), "in_reply_to")
    references = _references(payload.get("references"))
    provider_thread_id = _optional_text(
        payload.get("provider_thread_id"), "provider_thread_id"
    )
    provider_message_id = _optional_text(
        payload.get("provider_message_id"), "provider_message_id"
    )

    if in_reply_to is None and source_message_id is not None:
        in_reply_to = source_message_id
    if in_reply_to is not None and in_reply_to not in references:
        references.append(in_reply_to)

    explicit_evidence = any(
        (
            correspondence_id,
            thread_id,
            source_message_id,
            in_reply_to,
            references,
            provider_thread_id,
            provider_message_id,
        )
    )
    return {
        "contract": CONTRACT,
        "correspondence_id": correspondence_id,
        "thread_id": thread_id,
        "source_message_id": source_message_id,
        "in_reply_to": in_reply_to,
        "references": references,
        "provider_thread_id": provider_thread_id,
        "provider_message_id": provider_message_id,
        "correlation_strength": "explicit" if explicit_evidence else "none",
        "fallback_correlation_used": False,
    }


def apply_to_preview(preview: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    context = normalize_thread_context(payload)
    preview["threading"] = context
    preview["request"]["correspondence_id"] = context["correspondence_id"]
    preview["request"]["thread_id"] = context["thread_id"]
    preview["request"]["source_message_id"] = context["source_message_id"]
    preview["request"]["in_reply_to"] = context["in_reply_to"]
    preview["request"]["references"] = context["references"]
    preview["request"]["provider_thread_id"] = context["provider_thread_id"]
    preview["request"]["provider_message_id"] = context["provider_message_id"]

    if context["correspondence_id"]:
        preview["headers"]["X-WWCX-Correspondence-ID"] = context["correspondence_id"]
    if context["thread_id"]:
        preview["headers"]["X-WWCX-Thread-ID"] = context["thread_id"]
    if context["in_reply_to"]:
        preview["headers"]["In-Reply-To"] = context["in_reply_to"]
    if context["references"]:
        preview["headers"]["References"] = " ".join(context["references"])
    return preview
