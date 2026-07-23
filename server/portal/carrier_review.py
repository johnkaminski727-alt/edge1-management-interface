#!/usr/bin/env python3

"""Internal carrier-support review model for Phase 13I.

This module reads Phase 13H append-only intake records and appends internal
review events. It cannot approve, schedule, authorize, or execute changes.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REVIEW_READ_SCOPE = "internal.carrier.review.read"
REVIEW_WRITE_SCOPE = "internal.carrier.review.write"

RESOURCE_TYPES = frozenset({"ticket", "change_request"})
REVIEW_ACTIONS = frozenset({
    "acknowledge",
    "begin_review",
    "request_information",
    "close_ticket",
    "reject_change",
})
ACTION_STATUS = {
    "acknowledge": "acknowledged",
    "begin_review": "under_review",
    "request_information": "information_requested",
    "close_ticket": "closed",
    "reject_change": "rejected",
}
SAFE_RESOURCE_ID = re.compile(r"^(TKT|CRQ)-[A-F0-9]{12}$")
MAX_NOTE_LENGTH = 2000


class ReviewValidationError(ValueError):
    """Raised when an internal review request is invalid."""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ReviewValidationError(
                f"invalid JSONL record in {path.name} at line {line_number}"
            ) from error
        if not isinstance(record, dict):
            raise ReviewValidationError(
                f"non-object JSONL record in {path.name} at line {line_number}"
            )
        records.append(record)
    return records


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def _resource_id(record: dict[str, Any]) -> tuple[str, str] | None:
    if isinstance(record.get("ticket_id"), str):
        return "ticket", record["ticket_id"]
    if isinstance(record.get("change_request_id"), str):
        return "change_request", record["change_request_id"]
    return None


def build_review_queue(
    ticket_path: Path,
    change_path: Path,
    review_path: Path,
) -> dict[str, Any]:
    """Build a read-only internal queue with latest review state overlays."""

    source_records = _read_jsonl(ticket_path) + _read_jsonl(change_path)
    review_events = _read_jsonl(review_path)

    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for event in review_events:
        resource_type = event.get("resource_type")
        resource_id = event.get("resource_id")
        if resource_type in RESOURCE_TYPES and isinstance(resource_id, str):
            latest[(resource_type, resource_id)] = event

    items = []
    for source in source_records:
        identity = _resource_id(source)
        if identity is None:
            continue
        resource_type, resource_id = identity
        item = dict(source)
        item["resource_type"] = resource_type
        event = latest.get(identity)
        if event:
            item["review_status"] = event["status"]
            item["review_updated_at"] = event["created_at"]
            item["reviewed_by"] = event["reviewer_client_id"]
        else:
            item["review_status"] = "unreviewed"
        item["execution_authorized"] = False
        items.append(item)

    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return {
        "items": items,
        "count": len(items),
        "execution_authorized": False,
    }


def append_review_event(
    review_path: Path,
    ticket_path: Path,
    change_path: Path,
    reviewer_client_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Validate and append a non-executing internal review lifecycle event."""

    resource_type = payload.get("resource_type")
    if resource_type not in RESOURCE_TYPES:
        raise ReviewValidationError("resource_type must be ticket or change_request")

    resource_id = payload.get("resource_id")
    if not isinstance(resource_id, str) or not SAFE_RESOURCE_ID.fullmatch(resource_id):
        raise ReviewValidationError("resource_id is invalid")

    action = payload.get("action")
    if action not in REVIEW_ACTIONS:
        raise ReviewValidationError(
            "action must be acknowledge, begin_review, request_information, close_ticket, or reject_change"
        )
    if resource_type == "ticket" and action == "reject_change":
        raise ReviewValidationError("reject_change applies only to change requests")
    if resource_type == "change_request" and action == "close_ticket":
        raise ReviewValidationError("close_ticket applies only to tickets")

    note = payload.get("note", "")
    if not isinstance(note, str):
        raise ReviewValidationError("note must be a string")
    note = note.strip()
    if len(note) > MAX_NOTE_LENGTH:
        raise ReviewValidationError(f"note exceeds {MAX_NOTE_LENGTH} characters")

    sources = _read_jsonl(ticket_path if resource_type == "ticket" else change_path)
    expected_key = "ticket_id" if resource_type == "ticket" else "change_request_id"
    if not any(record.get(expected_key) == resource_id for record in sources):
        raise ReviewValidationError("resource not found")

    now = datetime.now(timezone.utc).isoformat()
    event = {
        "review_event_id": "REV-" + uuid.uuid4().hex[:12].upper(),
        "resource_type": resource_type,
        "resource_id": resource_id,
        "action": action,
        "status": ACTION_STATUS[action],
        "note": note,
        "reviewer_client_id": reviewer_client_id,
        "created_at": now,
        "approval_granted": False,
        "execution_authorized": False,
    }
    _append_jsonl(review_path, event)
    return event
