#!/usr/bin/env python3
"""Project Big Bird camera enrollment primitives.

This module owns only WW.CX / Big Bird enrollment identity. It deliberately
has no vendor activation-token or Wi-Fi credential handling. Vendor-specific
provisioning belongs behind a separate camera provisioning adapter after its
protocol has been verified.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

TOKEN_KIND = "bigbird_enrollment"
DEFAULT_TTL_SECONDS = 600
MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 3600

STATES = (
    "CREATED",
    "WAITING_FOR_PROVISIONING",
    "WAITING_FOR_CAMERA",
    "CAMERA_OBSERVED",
    "DEVICE_BOUND",
    "FIRST_FRAME_PENDING",
    "FIRST_FRAME_CAPTURED",
    "FAILED",
    "EXPIRED",
)

TERMINAL_STATES = {"FIRST_FRAME_CAPTURED", "FAILED", "EXPIRED"}

ALLOWED_TRANSITIONS = {
    "CREATED": {"WAITING_FOR_PROVISIONING", "FAILED", "EXPIRED"},
    "WAITING_FOR_PROVISIONING": {"WAITING_FOR_CAMERA", "FAILED", "EXPIRED"},
    "WAITING_FOR_CAMERA": {"CAMERA_OBSERVED", "FAILED", "EXPIRED"},
    "CAMERA_OBSERVED": {"DEVICE_BOUND", "WAITING_FOR_CAMERA", "FAILED", "EXPIRED"},
    "DEVICE_BOUND": {"FIRST_FRAME_PENDING", "FAILED", "EXPIRED"},
    "FIRST_FRAME_PENDING": {"FIRST_FRAME_CAPTURED", "FAILED", "EXPIRED"},
    "FIRST_FRAME_CAPTURED": set(),
    "FAILED": set(),
    "EXPIRED": set(),
}


class EnrollmentError(RuntimeError):
    """Base enrollment exception."""


class EnrollmentExpired(EnrollmentError):
    """Enrollment has expired."""


class EnrollmentTokenRejected(EnrollmentError):
    """Enrollment token is invalid or already consumed."""


@dataclass(frozen=True)
class CreatedEnrollment:
    session_id: str
    token: str
    token_kind: str
    expires_at: int
    state: str


def _now(now: Optional[int] = None) -> int:
    return int(time.time() if now is None else now)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _validate_ttl(ttl_seconds: int) -> int:
    ttl = int(ttl_seconds)
    if ttl < MIN_TTL_SECONDS or ttl > MAX_TTL_SECONDS:
        raise ValueError("enrollment TTL is outside the allowed range")
    return ttl


def _validate_camera_type(camera_type: str) -> str:
    value = camera_type.strip().lower()
    if not value or len(value) > 64:
        raise ValueError("camera type is invalid")
    if any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for ch in value):
        raise ValueError("camera type is invalid")
    return value


def _validate_method(method: str) -> str:
    value = method.strip().lower()
    allowed = {"qr", "ap", "smartconfig", "local", "vendor_supported", "unknown"}
    if value not in allowed:
        raise ValueError("provisioning method is unsupported")
    return value


def connect(path: str = ":memory:") -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    migrate(db)
    return db


def migrate(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS camera_enrollments (
            session_id TEXT PRIMARY KEY,
            token_kind TEXT NOT NULL,
            token_digest TEXT NOT NULL,
            token_consumed_at INTEGER,
            camera_type TEXT NOT NULL,
            provisioning_method TEXT NOT NULL,
            state TEXT NOT NULL,
            observed_device_json TEXT,
            durable_device_id TEXT,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            CHECK (token_kind = 'bigbird_enrollment')
        );
        CREATE INDEX IF NOT EXISTS idx_camera_enrollments_expiry
            ON camera_enrollments(expires_at, state);
        CREATE TABLE IF NOT EXISTS camera_enrollment_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            event TEXT NOT NULL,
            detail_json TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY(session_id) REFERENCES camera_enrollments(session_id)
        );
        """
    )
    db.commit()


def _audit(db: sqlite3.Connection, session_id: str, event: str, detail: Dict[str, Any], now: int) -> None:
    forbidden = {"token", "wifi_password", "password", "vendor_activation_token"}
    if forbidden.intersection(detail):
        raise EnrollmentError("secret-like audit field rejected")
    db.execute(
        "INSERT INTO camera_enrollment_audit(session_id,event,detail_json,created_at) VALUES(?,?,?,?)",
        (session_id, event, json.dumps(detail, sort_keys=True, separators=(",", ":")), now),
    )


def create_enrollment(
    db: sqlite3.Connection,
    camera_type: str,
    provisioning_method: str = "unknown",
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: Optional[int] = None,
) -> CreatedEnrollment:
    created_at = _now(now)
    ttl = _validate_ttl(ttl_seconds)
    camera = _validate_camera_type(camera_type)
    method = _validate_method(provisioning_method)
    session_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    expires_at = created_at + ttl
    db.execute(
        """
        INSERT INTO camera_enrollments(
            session_id,token_kind,token_digest,token_consumed_at,camera_type,
            provisioning_method,state,observed_device_json,durable_device_id,
            created_at,expires_at,updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            session_id,
            TOKEN_KIND,
            _digest(token),
            None,
            camera,
            method,
            "CREATED",
            None,
            None,
            created_at,
            expires_at,
            created_at,
        ),
    )
    _audit(db, session_id, "enrollment_created", {"camera_type": camera, "provisioning_method": method}, created_at)
    db.commit()
    return CreatedEnrollment(session_id, token, TOKEN_KIND, expires_at, "CREATED")


def get_enrollment(db: sqlite3.Connection, session_id: str) -> Dict[str, Any]:
    row = db.execute("SELECT * FROM camera_enrollments WHERE session_id=?", (session_id,)).fetchone()
    if row is None:
        raise EnrollmentError("enrollment not found")
    result = dict(row)
    result.pop("token_digest", None)
    if result.get("observed_device_json"):
        result["observed_device"] = json.loads(result.pop("observed_device_json"))
    else:
        result.pop("observed_device_json", None)
        result["observed_device"] = None
    return result


def expire_if_needed(db: sqlite3.Connection, session_id: str, now: Optional[int] = None) -> bool:
    current = _now(now)
    row = db.execute("SELECT state,expires_at FROM camera_enrollments WHERE session_id=?", (session_id,)).fetchone()
    if row is None:
        raise EnrollmentError("enrollment not found")
    if row["state"] in TERMINAL_STATES:
        return row["state"] == "EXPIRED"
    if current < int(row["expires_at"]):
        return False
    db.execute("UPDATE camera_enrollments SET state='EXPIRED',updated_at=? WHERE session_id=?", (current, session_id))
    _audit(db, session_id, "enrollment_expired", {}, current)
    db.commit()
    return True


def consume_enrollment_token(
    db: sqlite3.Connection,
    session_id: str,
    token: str,
    now: Optional[int] = None,
) -> None:
    current = _now(now)
    if expire_if_needed(db, session_id, current):
        raise EnrollmentExpired("enrollment expired")
    row = db.execute(
        "SELECT token_digest,token_consumed_at,token_kind FROM camera_enrollments WHERE session_id=?",
        (session_id,),
    ).fetchone()
    if row is None:
        raise EnrollmentError("enrollment not found")
    if row["token_kind"] != TOKEN_KIND:
        raise EnrollmentTokenRejected("token namespace mismatch")
    if row["token_consumed_at"] is not None:
        raise EnrollmentTokenRejected("enrollment token already consumed")
    if not isinstance(token, str) or not hmac.compare_digest(row["token_digest"], _digest(token)):
        raise EnrollmentTokenRejected("enrollment token rejected")
    cursor = db.execute(
        "UPDATE camera_enrollments SET token_consumed_at=?,updated_at=? WHERE session_id=? AND token_consumed_at IS NULL",
        (current, current, session_id),
    )
    if cursor.rowcount != 1:
        db.rollback()
        raise EnrollmentTokenRejected("enrollment token already consumed")
    _audit(db, session_id, "enrollment_token_consumed", {"token_kind": TOKEN_KIND}, current)
    db.commit()


def transition(db: sqlite3.Connection, session_id: str, new_state: str, now: Optional[int] = None) -> None:
    current = _now(now)
    if new_state not in STATES:
        raise EnrollmentError("unknown enrollment state")
    if expire_if_needed(db, session_id, current):
        if new_state != "EXPIRED":
            raise EnrollmentExpired("enrollment expired")
        return
    row = db.execute("SELECT state FROM camera_enrollments WHERE session_id=?", (session_id,)).fetchone()
    if row is None:
        raise EnrollmentError("enrollment not found")
    old_state = row["state"]
    if new_state == old_state:
        return
    if new_state not in ALLOWED_TRANSITIONS[old_state]:
        raise EnrollmentError(f"invalid enrollment transition: {old_state} -> {new_state}")
    db.execute("UPDATE camera_enrollments SET state=?,updated_at=? WHERE session_id=?", (new_state, current, session_id))
    _audit(db, session_id, "state_changed", {"from": old_state, "to": new_state}, current)
    db.commit()


def record_observed_device(
    db: sqlite3.Connection,
    session_id: str,
    *,
    ip: Optional[str] = None,
    mac: Optional[str] = None,
    hostname: Optional[str] = None,
    now: Optional[int] = None,
) -> None:
    current = _now(now)
    row = db.execute("SELECT state FROM camera_enrollments WHERE session_id=?", (session_id,)).fetchone()
    if row is None:
        raise EnrollmentError("enrollment not found")
    if row["state"] != "WAITING_FOR_CAMERA":
        raise EnrollmentError("camera observation is not expected in the current state")
    observed = {key: value for key, value in (("ip", ip), ("mac", mac), ("hostname", hostname)) if value}
    if not observed:
        raise EnrollmentError("at least one observed device identifier is required")
    encoded = json.dumps(observed, sort_keys=True, separators=(",", ":"))
    db.execute(
        "UPDATE camera_enrollments SET observed_device_json=?,state='CAMERA_OBSERVED',updated_at=? WHERE session_id=?",
        (encoded, current, session_id),
    )
    _audit(db, session_id, "camera_observed", {"identifiers": sorted(observed)}, current)
    db.commit()


def bind_device(db: sqlite3.Connection, session_id: str, durable_device_id: str, now: Optional[int] = None) -> None:
    current = _now(now)
    if not durable_device_id or len(durable_device_id) > 128:
        raise EnrollmentError("durable device identifier is invalid")
    row = db.execute("SELECT state FROM camera_enrollments WHERE session_id=?", (session_id,)).fetchone()
    if row is None or row["state"] != "CAMERA_OBSERVED":
        raise EnrollmentError("camera must be observed before device binding")
    db.execute(
        "UPDATE camera_enrollments SET durable_device_id=?,state='DEVICE_BOUND',updated_at=? WHERE session_id=?",
        (durable_device_id, current, session_id),
    )
    _audit(db, session_id, "device_bound", {"durable_device_id": durable_device_id}, current)
    db.commit()


def audit_events(db: sqlite3.Connection, session_id: str) -> Iterable[Dict[str, Any]]:
    rows = db.execute(
        "SELECT event,detail_json,created_at FROM camera_enrollment_audit WHERE session_id=? ORDER BY id",
        (session_id,),
    ).fetchall()
    for row in rows:
        yield {"event": row["event"], "detail": json.loads(row["detail_json"]), "created_at": row["created_at"]}
