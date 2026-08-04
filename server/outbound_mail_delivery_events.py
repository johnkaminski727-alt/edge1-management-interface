#!/usr/bin/env python3
"""Provider-neutral outbound-mail delivery events and suppression state.

The module stores minimized event metadata and recipient hashes only. It does
not expose a network listener, contact a provider, inspect credentials, store
message content, or send mail. Permanent bounces, complaints and unsubscribe
events create durable suppressions that are never cleared automatically.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


CONTRACT = "wwcx.outbound-mail-delivery-event.v1"
EVENT_TYPES = {
    "provider_accepted",
    "delivered",
    "transient_bounce",
    "permanent_bounce",
    "complaint",
    "unsubscribe",
    "provider_rejected",
}
SOURCE_AUTHENTICATION = {
    "provider_signature",
    "authenticated_mailbox_dsn",
    "manual_evidence_import",
    "synthetic_test",
}
DIAGNOSTIC_CLASSES = {
    "none",
    "mailbox_unavailable",
    "domain_unavailable",
    "policy_rejection",
    "spam_complaint",
    "user_unsubscribe",
    "rate_limited",
    "provider_unavailable",
    "unknown",
}
SUPPRESSIVE_TYPES = {"permanent_bounce", "complaint", "unsubscribe"}
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,63}$")
CONTROL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,159}$")


class DeliveryEventError(RuntimeError):
    """Base class for delivery-event failures."""


class DeliveryEventValidationError(DeliveryEventError):
    """Raised when an event is malformed or unsafe."""


class DeliveryEventConflictError(DeliveryEventError):
    """Raised when an event ID is reused with different evidence."""


@dataclass(frozen=True)
class ApplyResult:
    event_id: str
    duplicate: bool
    recipient_sha256: str
    event_type: str
    suppression_active: bool
    suppression_reason: str | None
    transient_failure_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "duplicate": self.duplicate,
            "recipient_sha256": self.recipient_sha256,
            "event_type": self.event_type,
            "suppression_active": self.suppression_active,
            "suppression_reason": self.suppression_reason,
            "transient_failure_count": self.transient_failure_count,
        }


def canonical_event_bytes(event: dict[str, Any]) -> bytes:
    return json.dumps(
        event,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def event_sha256(event: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_event_bytes(event)).hexdigest()


def _require_exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DeliveryEventValidationError(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        raise DeliveryEventValidationError(
            f"{label} keys invalid; missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise DeliveryEventValidationError(f"{label} must be boolean")
    return value


def _require_pattern(value: Any, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise DeliveryEventValidationError(f"{label} is invalid")
    return value


def _require_timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str) or "T" not in value or not (
        value.endswith("Z") or "+" in value[10:]
    ):
        raise DeliveryEventValidationError(f"{label} must be an ISO-8601 timestamp")
    return value


def validate_event(event: dict[str, Any], *, allow_synthetic: bool = False) -> dict[str, Any]:
    value = _require_exact_keys(
        event,
        {
            "contract",
            "event_id",
            "event_type",
            "occurred_at",
            "provider_profile",
            "provider_message_id_sha256",
            "control_id",
            "recipient_sha256",
            "source_evidence_sha256",
            "source_authentication",
            "source_verified",
            "diagnostic_class",
            "retryable",
            "raw_recipient_stored",
            "raw_payload_stored",
            "message_content_stored",
        },
        "delivery event",
    )
    if value["contract"] != CONTRACT:
        raise DeliveryEventValidationError("unsupported delivery-event contract")
    _require_pattern(value["event_id"], EVENT_ID_RE, "event_id")
    if value["event_type"] not in EVENT_TYPES:
        raise DeliveryEventValidationError("event_type is unsupported")
    _require_timestamp(value["occurred_at"], "occurred_at")
    _require_pattern(value["provider_profile"], PROFILE_RE, "provider_profile")
    _require_pattern(
        value["provider_message_id_sha256"],
        HEX64_RE,
        "provider_message_id_sha256",
    )
    _require_pattern(value["control_id"], CONTROL_ID_RE, "control_id")
    _require_pattern(value["recipient_sha256"], HEX64_RE, "recipient_sha256")
    _require_pattern(value["source_evidence_sha256"], HEX64_RE, "source_evidence_sha256")
    if value["source_authentication"] not in SOURCE_AUTHENTICATION:
        raise DeliveryEventValidationError("source_authentication is unsupported")
    if value["source_authentication"] == "synthetic_test" and not allow_synthetic:
        raise DeliveryEventValidationError("synthetic delivery events are not allowed")
    if value["diagnostic_class"] not in DIAGNOSTIC_CLASSES:
        raise DeliveryEventValidationError("diagnostic_class is unsupported")
    for key in (
        "source_verified",
        "retryable",
        "raw_recipient_stored",
        "raw_payload_stored",
        "message_content_stored",
    ):
        _require_bool(value[key], key)
    if not value["source_verified"]:
        raise DeliveryEventValidationError("delivery-event source is not verified")
    if any(
        value[key]
        for key in ("raw_recipient_stored", "raw_payload_stored", "message_content_stored")
    ):
        raise DeliveryEventValidationError("delivery event contains prohibited raw data")

    event_type = value["event_type"]
    if value["retryable"] != (event_type == "transient_bounce"):
        raise DeliveryEventValidationError("retryable flag does not match event_type")
    expected_diagnostic = {
        "provider_accepted": {"none"},
        "delivered": {"none"},
        "transient_bounce": {
            "mailbox_unavailable",
            "domain_unavailable",
            "rate_limited",
            "provider_unavailable",
            "unknown",
        },
        "permanent_bounce": {
            "mailbox_unavailable",
            "domain_unavailable",
            "policy_rejection",
            "unknown",
        },
        "complaint": {"spam_complaint"},
        "unsubscribe": {"user_unsubscribe"},
        "provider_rejected": {
            "policy_rejection",
            "rate_limited",
            "provider_unavailable",
            "unknown",
        },
    }[event_type]
    if value["diagnostic_class"] not in expected_diagnostic:
        raise DeliveryEventValidationError(
            "diagnostic_class is inconsistent with event_type"
        )
    return value


def _connect(path: str | Path) -> sqlite3.Connection:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(target), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS delivery_events (
            event_id TEXT PRIMARY KEY,
            event_sha256 TEXT NOT NULL,
            event_type TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            provider_profile TEXT NOT NULL,
            provider_message_id_sha256 TEXT NOT NULL,
            control_id TEXT NOT NULL,
            recipient_sha256 TEXT NOT NULL,
            source_evidence_sha256 TEXT NOT NULL,
            source_authentication TEXT NOT NULL,
            diagnostic_class TEXT NOT NULL,
            retryable INTEGER NOT NULL CHECK (retryable IN (0,1)),
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_delivery_events_recipient
            ON delivery_events(recipient_sha256, occurred_at);
        CREATE INDEX IF NOT EXISTS idx_delivery_events_provider_message
            ON delivery_events(provider_message_id_sha256);
        CREATE TABLE IF NOT EXISTS recipient_delivery_state (
            recipient_sha256 TEXT PRIMARY KEY,
            suppression_active INTEGER NOT NULL DEFAULT 0
                CHECK (suppression_active IN (0,1)),
            suppression_reason TEXT,
            first_suppression_event_id TEXT,
            last_event_id TEXT NOT NULL,
            last_event_type TEXT NOT NULL,
            last_occurred_at TEXT NOT NULL,
            event_count INTEGER NOT NULL DEFAULT 0,
            transient_failure_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(first_suppression_event_id) REFERENCES delivery_events(event_id),
            FOREIGN KEY(last_event_id) REFERENCES delivery_events(event_id)
        );
        """
    )
    return connection


def _state_row(connection: sqlite3.Connection, recipient_sha256: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM recipient_delivery_state WHERE recipient_sha256=?",
        (recipient_sha256,),
    ).fetchone()


def _result_from_state(
    event: dict[str, Any],
    duplicate: bool,
    state: sqlite3.Row | None,
) -> ApplyResult:
    return ApplyResult(
        event_id=event["event_id"],
        duplicate=duplicate,
        recipient_sha256=event["recipient_sha256"],
        event_type=event["event_type"],
        suppression_active=bool(state["suppression_active"]) if state else False,
        suppression_reason=str(state["suppression_reason"]) if state and state["suppression_reason"] else None,
        transient_failure_count=int(state["transient_failure_count"]) if state else 0,
    )


def apply_event(
    database: str | Path,
    event: dict[str, Any],
    *,
    allow_synthetic: bool = False,
) -> ApplyResult:
    value = validate_event(event, allow_synthetic=allow_synthetic)
    digest = event_sha256(value)
    connection = _connect(database)
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT event_sha256 FROM delivery_events WHERE event_id=?",
            (value["event_id"],),
        ).fetchone()
        if existing is not None:
            if existing["event_sha256"] != digest:
                connection.rollback()
                raise DeliveryEventConflictError(
                    "delivery event ID was reused with different evidence"
                )
            state = _state_row(connection, value["recipient_sha256"])
            connection.rollback()
            return _result_from_state(value, True, state)

        connection.execute(
            """
            INSERT INTO delivery_events(
                event_id,event_sha256,event_type,occurred_at,provider_profile,
                provider_message_id_sha256,control_id,recipient_sha256,
                source_evidence_sha256,source_authentication,diagnostic_class,retryable
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                value["event_id"],
                digest,
                value["event_type"],
                value["occurred_at"],
                value["provider_profile"],
                value["provider_message_id_sha256"],
                value["control_id"],
                value["recipient_sha256"],
                value["source_evidence_sha256"],
                value["source_authentication"],
                value["diagnostic_class"],
                int(value["retryable"]),
            ),
        )

        previous = _state_row(connection, value["recipient_sha256"])
        active = bool(previous["suppression_active"]) if previous else False
        reason = str(previous["suppression_reason"]) if previous and previous["suppression_reason"] else None
        first_suppression = (
            str(previous["first_suppression_event_id"])
            if previous and previous["first_suppression_event_id"]
            else None
        )
        event_count = int(previous["event_count"]) if previous else 0
        transient_count = int(previous["transient_failure_count"]) if previous else 0

        if value["event_type"] in SUPPRESSIVE_TYPES:
            active = True
            reason = value["event_type"]
            first_suppression = first_suppression or value["event_id"]
        elif value["event_type"] == "transient_bounce":
            transient_count += 1
        elif value["event_type"] == "delivered" and not active:
            transient_count = 0

        connection.execute(
            """
            INSERT INTO recipient_delivery_state(
                recipient_sha256,suppression_active,suppression_reason,
                first_suppression_event_id,last_event_id,last_event_type,
                last_occurred_at,event_count,transient_failure_count
            ) VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(recipient_sha256) DO UPDATE SET
                suppression_active=excluded.suppression_active,
                suppression_reason=excluded.suppression_reason,
                first_suppression_event_id=excluded.first_suppression_event_id,
                last_event_id=excluded.last_event_id,
                last_event_type=excluded.last_event_type,
                last_occurred_at=excluded.last_occurred_at,
                event_count=excluded.event_count,
                transient_failure_count=excluded.transient_failure_count
            """,
            (
                value["recipient_sha256"],
                int(active),
                reason,
                first_suppression,
                value["event_id"],
                value["event_type"],
                value["occurred_at"],
                event_count + 1,
                transient_count,
            ),
        )
        state = _state_row(connection, value["recipient_sha256"])
        connection.commit()
    finally:
        connection.close()
    try:
        os.chmod(database, 0o600)
    except OSError:
        pass
    return _result_from_state(value, False, state)


def recipient_state(database: str | Path, recipient_sha256: str) -> dict[str, Any]:
    _require_pattern(recipient_sha256, HEX64_RE, "recipient_sha256")
    path = Path(database)
    if not path.is_file():
        return {
            "recipient_sha256": recipient_sha256,
            "suppression_active": False,
            "suppression_reason": None,
            "event_count": 0,
            "transient_failure_count": 0,
            "last_event_id": None,
            "last_event_type": None,
            "last_occurred_at": None,
        }
    connection = _connect(path)
    try:
        state = _state_row(connection, recipient_sha256)
    finally:
        connection.close()
    if state is None:
        return {
            "recipient_sha256": recipient_sha256,
            "suppression_active": False,
            "suppression_reason": None,
            "event_count": 0,
            "transient_failure_count": 0,
            "last_event_id": None,
            "last_event_type": None,
            "last_occurred_at": None,
        }
    return {
        "recipient_sha256": recipient_sha256,
        "suppression_active": bool(state["suppression_active"]),
        "suppression_reason": state["suppression_reason"],
        "event_count": int(state["event_count"]),
        "transient_failure_count": int(state["transient_failure_count"]),
        "last_event_id": state["last_event_id"],
        "last_event_type": state["last_event_type"],
        "last_occurred_at": state["last_occurred_at"],
    }


def suppressed_recipients(
    database: str | Path,
    recipient_hashes: Iterable[str],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for recipient_hash in recipient_hashes:
        state = recipient_state(database, recipient_hash)
        if state["suppression_active"]:
            results.append(state)
    return results
