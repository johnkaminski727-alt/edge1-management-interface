#!/usr/bin/env python3

"""Append-only carrier ticket and change-request workflows.

Phase 13H records carrier requests for later internal review. It never applies
routing, numbering, credential, firewall, certificate, or traffic changes.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TICKET_SCOPE = "carrier.ticket.create"
CHANGE_SCOPE = "carrier.change.request"

TICKET_CATEGORIES = frozenset({
    "incident",
    "interconnect",
    "numbering",
    "billing",
    "general",
})

CHANGE_CATEGORIES = frozenset({
    "sip_ip_update",
    "capacity_change",
    "routing_preference",
    "interconnect_modification",
    "testing_request",
})

PRIORITIES = frozenset({"low", "normal", "high", "urgent"})
MAX_SUMMARY_LENGTH = 160
MAX_DESCRIPTION_LENGTH = 4000
SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9._:/+-]{1,128}$")


class WorkflowValidationError(ValueError):
    """Raised when an incoming carrier workflow request is invalid."""


@dataclass(frozen=True)
class WorkflowIdentity:
    client_id: str
    carrier_id: str


def _required_text(payload: dict[str, Any], key: str, maximum: int) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise WorkflowValidationError(f"{key} is required")
    value = value.strip()
    if not value:
        raise WorkflowValidationError(f"{key} is required")
    if len(value) > maximum:
        raise WorkflowValidationError(f"{key} exceeds {maximum} characters")
    return value


def _optional_reference(payload: dict[str, Any]) -> str | None:
    value = payload.get("reference")
    if value is None:
        return None
    if not isinstance(value, str) or not SAFE_REFERENCE.fullmatch(value.strip()):
        raise WorkflowValidationError("reference contains unsupported characters")
    return value.strip()


def _choice(payload: dict[str, Any], key: str, choices: frozenset[str], default: str | None = None) -> str:
    value = payload.get(key, default)
    if not isinstance(value, str) or value not in choices:
        allowed = ", ".join(sorted(choices))
        raise WorkflowValidationError(f"{key} must be one of: {allowed}")
    return value


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")


def create_ticket(path: Path, identity: WorkflowIdentity, payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "ticket_id": "TKT-" + uuid.uuid4().hex[:12].upper(),
        "carrier_id": identity.carrier_id,
        "client_id": identity.client_id,
        "category": _choice(payload, "category", TICKET_CATEGORIES),
        "priority": _choice(payload, "priority", PRIORITIES, "normal"),
        "summary": _required_text(payload, "summary", MAX_SUMMARY_LENGTH),
        "description": _required_text(payload, "description", MAX_DESCRIPTION_LENGTH),
        "reference": _optional_reference(payload),
        "status": "open",
        "created_at": now,
        "updated_at": now,
    }
    _append_jsonl(path, record)
    return record


def create_change_request(path: Path, identity: WorkflowIdentity, payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "change_request_id": "CRQ-" + uuid.uuid4().hex[:12].upper(),
        "carrier_id": identity.carrier_id,
        "client_id": identity.client_id,
        "category": _choice(payload, "category", CHANGE_CATEGORIES),
        "priority": _choice(payload, "priority", PRIORITIES, "normal"),
        "summary": _required_text(payload, "summary", MAX_SUMMARY_LENGTH),
        "description": _required_text(payload, "description", MAX_DESCRIPTION_LENGTH),
        "reference": _optional_reference(payload),
        "status": "requested",
        "execution_authorized": False,
        "created_at": now,
        "updated_at": now,
    }
    _append_jsonl(path, record)
    return record
