#!/usr/bin/env python3
"""Bounded read-only Unified Contacts adapter for Ava gateway integration."""

from __future__ import annotations

import json
import urllib.parse
from typing import Any

from server.phone_intelligence_gateway import (
    GatewayError,
    credential_path,
    read_secret,
    signed_get,
)

DEFAULT_LIMIT = 12
MAX_LIMIT = 25
ALLOWED_KINDS = {"all", "organizations", "people", "phones", "emails"}

SAFE_RESULT_KEYS = {
    "entity_id",
    "entity_type",
    "canonical_name",
    "display_name",
    "verification_status",
    "assertion_id",
    "confidence",
    "assertion_type",
    "contact_point_id",
    "point_type",
    "normalized_value",
    "display_value",
    "lifecycle_status",
}


class AvaContactsError(RuntimeError):
    pass


def normalize_kind(kind: str | None) -> str:
    value = (kind or "all").strip().lower()
    if value not in ALLOWED_KINDS:
        raise AvaContactsError("unsupported contacts kind")
    return value


def clamp_limit(limit: int | str | None) -> int:
    try:
        value = int(limit if limit is not None else DEFAULT_LIMIT)
    except (TypeError, ValueError):
        value = DEFAULT_LIMIT
    return max(1, min(value, MAX_LIMIT))


def sanitize_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    clean: dict[str, Any] = {}
    for key in SAFE_RESULT_KEYS:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
    return clean


def search_contacts(
    query: str,
    *,
    kind: str = "all",
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    q = query.strip()
    if not q:
        return []

    normalized_kind = normalize_kind(kind)
    bounded_limit = clamp_limit(limit)

    upstream_path = "/v1/contacts/search?" + urllib.parse.urlencode(
        {
            "q": q,
            "kind": normalized_kind,
            "limit": bounded_limit,
        }
    )

    try:
        secret = read_secret(credential_path())
        status, raw = signed_get(
            upstream_path,
            secret=secret,
            actor="ava-contacts-gateway",
        )
    except GatewayError as exc:
        raise AvaContactsError("Unified Contacts backend unavailable") from exc

    if status != 200:
        raise AvaContactsError(f"Unified Contacts returned HTTP {status}")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AvaContactsError("Unified Contacts returned invalid JSON") from exc

    if not isinstance(payload, list):
        raise AvaContactsError("Unified Contacts returned an invalid result shape")

    results: list[dict[str, Any]] = []
    for row in payload[:bounded_limit]:
        clean = sanitize_row(row)
        if not clean:
            continue

        # Stable source metadata used by Ava evidence accounting. Confidence
        # and verification stay separate so probable evidence is never
        # promoted to confirmed identity.
        source_id = "contact:"
        if "assertion_id" in clean:
            source_id += f"assertion:{clean['assertion_id']}"
        elif "contact_point_id" in clean:
            source_id += f"point:{clean['contact_point_id']}"
        elif "entity_id" in clean:
            source_id += f"entity:{clean['entity_id']}"
        else:
            continue

        clean["source_id"] = source_id
        clean["source_name"] = "Edge1 Unified Contacts"
        results.append(clean)

    return results
