#!/usr/bin/env python3

"""Carrier-scoped operational views for the Phase 13G portal integration.

The module operates only on exported JSON summaries. It does not expose Edge1
credentials, private network topology, or permit production routing changes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


READ_ONLY_SCOPES = frozenset({
    "carrier.profile.read",
    "carrier.interconnect.read",
    "carrier.numbering.read",
    "carrier.metrics.read",
    "carrier.monitoring.read",
})

ENDPOINT_SCOPES = {
    "/portal/carrier/profile": "carrier.profile.read",
    "/portal/carrier/interconnects": "carrier.interconnect.read",
    "/portal/carrier/numbers": "carrier.numbering.read",
    "/portal/carrier/metrics": "carrier.metrics.read",
    "/portal/carrier/monitoring": "carrier.monitoring.read",
}

SOURCE_FILES = {
    "/portal/carrier/profile": "carrier-status.json",
    "/portal/carrier/interconnects": "interconnect-status.json",
    "/portal/carrier/numbers": "numbering-status.json",
    "/portal/carrier/metrics": "health-summary.json",
    "/portal/carrier/monitoring": "health-summary.json",
}

SENSITIVE_KEYS = frozenset({
    "secret",
    "password",
    "credential",
    "credentials",
    "private_key",
    "api_key",
    "auth_token",
    "internal_ip",
    "management_ip",
    "network_topology",
})

CARRIER_KEYS = ("carrier_id", "carrier", "carrier_slug", "tenant_id")


@dataclass(frozen=True)
class PortalIdentity:
    client_id: str
    carrier_id: str | None
    scopes: frozenset[str]

    def permits(self, endpoint: str) -> bool:
        required = ENDPOINT_SCOPES.get(endpoint)
        return required is not None and required in self.scopes


def identity_from_config(client_id: str, client: dict[str, Any]) -> PortalIdentity:
    """Resolve a client identity without returning secret configuration fields."""

    configured_scopes = client.get("scopes")
    if configured_scopes is None:
        configured_scopes = sorted(READ_ONLY_SCOPES)

    scopes = frozenset(str(scope) for scope in configured_scopes)
    carrier_id = client.get("carrier_id")
    if carrier_id is not None:
        carrier_id = str(carrier_id)

    return PortalIdentity(client_id=client_id, carrier_id=carrier_id, scopes=scopes)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _record_carrier(record: dict[str, Any]) -> str | None:
    for key in CARRIER_KEYS:
        value = record.get(key)
        if value is not None:
            return str(value)
    return None


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize(item)
            for key, item in value.items()
            if key.lower() not in SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _filter_records(records: Iterable[Any], carrier_id: str) -> list[Any]:
    filtered: list[Any] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if _record_carrier(record) == carrier_id:
            filtered.append(_sanitize(record))
    return filtered


def carrier_scope(payload: Any, carrier_id: str | None) -> Any:
    """Return only records owned by a carrier and remove sensitive fields.

    A carrier identity is required for operational endpoints. Supported export
    shapes are a top-level list, a single carrier record, or a dictionary whose
    list-valued sections contain carrier-owned records.
    """

    if not carrier_id:
        raise PermissionError("carrier identity is required")

    if isinstance(payload, list):
        return _filter_records(payload, carrier_id)

    if not isinstance(payload, dict):
        return payload

    payload_carrier = _record_carrier(payload)
    if payload_carrier is not None:
        if payload_carrier != carrier_id:
            return {}
        return _sanitize(payload)

    result: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in SENSITIVE_KEYS:
            continue
        if isinstance(value, list):
            result[key] = _filter_records(value, carrier_id)
        elif isinstance(value, dict):
            nested_carrier = _record_carrier(value)
            if nested_carrier is None or nested_carrier == carrier_id:
                result[key] = _sanitize(value)
        else:
            result[key] = value

    result["carrier_id"] = carrier_id
    return result


def operational_response(portal_dir: Path, endpoint: str, identity: PortalIdentity) -> Any:
    if endpoint not in SOURCE_FILES:
        raise KeyError(endpoint)
    if not identity.permits(endpoint):
        raise PermissionError("scope denied")

    payload = load_json(portal_dir / SOURCE_FILES[endpoint])
    return carrier_scope(payload, identity.carrier_id)
