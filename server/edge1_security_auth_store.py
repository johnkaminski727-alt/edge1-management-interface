"""Edge1-owned replay, opaque-session, and append-only audit storage."""
from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional

from .edge1_security_auth_core import (
    AssertionIdentity,
    AuditUnavailableError,
    AuthenticationError,
    SessionContext,
    valid_event_id,
)


class JsonlAuditSink:
    """Append-only JSONL sink that never receives tokens or assertions."""

    def __init__(self, path: Path):
        self.path = path

    def __call__(self, event: Mapping[str, Any]) -> str:
        record = dict(event)
        event_id = record.get("event_id") or f"edge1-auth-{uuid.uuid4().hex}"
        if not valid_event_id(event_id):
            raise AuditUnavailableError("audit event identifier is invalid")
        record["event_id"] = event_id
        record.setdefault("timestamp", int(time.time()))
        forbidden = {"assertion", "token", "cookie", "password", "signature", "private_key"}
        if forbidden.intersection(record):
            raise AuditUnavailableError("audit record contains prohibited fields")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(self.path.parent, 0o700)
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                payload = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
                os.write(fd, payload.encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)
            os.chmod(self.path, 0o600)
        except OSError as exc:
            raise AuditUnavailableError("required audit evidence could not be written") from exc
        return str(event_id)


class SQLiteGatewayStore:
    """Atomic replay and hashed opaque-session storage owned by Edge1."""

    def __init__(self, path: Path):
        self.path = path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _initialize(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(self.path.parent, 0o700)
            with contextlib.closing(self._connect()) as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS assertion_replay (
                        jti_hash TEXT PRIMARY KEY,
                        expires_at INTEGER NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_hash TEXT PRIMARY KEY,
                        subject TEXT NOT NULL,
                        display_name TEXT NOT NULL,
                        source_role TEXT NOT NULL,
                        scopes_json TEXT NOT NULL,
                        issued_at INTEGER NOT NULL,
                        expires_at INTEGER NOT NULL,
                        last_seen_at INTEGER NOT NULL,
                        assertion_jti_hash TEXT NOT NULL,
                        authentication_event_id TEXT NOT NULL,
                        revoked_at INTEGER
                    );
                    CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);
                    """
                )
            os.chmod(self.path, 0o600)
        except (OSError, sqlite3.Error) as exc:
            raise AuthenticationError("session store is unavailable") from exc

    def consume_assertion(self, jti_hash: str, expires_at: int, now: int) -> bool:
        try:
            with contextlib.closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM assertion_replay WHERE expires_at < ?", (now,))
                try:
                    connection.execute(
                        "INSERT INTO assertion_replay(jti_hash, expires_at) VALUES (?, ?)",
                        (jti_hash, expires_at),
                    )
                except sqlite3.IntegrityError:
                    connection.execute("ROLLBACK")
                    return False
                connection.execute("COMMIT")
            return True
        except sqlite3.Error as exc:
            raise AuthenticationError("assertion replay store is unavailable") from exc

    def create_session(
        self,
        *,
        session_hash: str,
        identity: AssertionIdentity,
        issued_at: int,
        expires_at: int,
        authentication_event_id: str,
    ) -> None:
        try:
            with contextlib.closing(self._connect()) as connection:
                connection.execute(
                    """
                    INSERT INTO sessions(
                        session_hash, subject, display_name, source_role, scopes_json,
                        issued_at, expires_at, last_seen_at, assertion_jti_hash,
                        authentication_event_id, revoked_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        session_hash, identity.subject, identity.display_name,
                        identity.source_role,
                        json.dumps(sorted(identity.scopes), separators=(",", ":")),
                        issued_at, expires_at, issued_at, identity.jti_hash,
                        authentication_event_id,
                    ),
                )
        except sqlite3.Error as exc:
            raise AuthenticationError("session could not be created") from exc

    def resolve_session(
        self, session_hash: str, now: int, idle_timeout: int
    ) -> tuple[Optional[SessionContext], str]:
        try:
            with contextlib.closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM sessions WHERE session_hash = ?", (session_hash,)
                ).fetchone()
                if row is None:
                    connection.execute("ROLLBACK")
                    return None, "unknown_session"
                reason = "active"
                if row["revoked_at"] is not None:
                    reason = "revoked"
                elif now >= int(row["expires_at"]):
                    reason = "expired"
                elif now - int(row["last_seen_at"]) >= idle_timeout:
                    reason = "idle_expired"
                if reason != "active":
                    connection.execute(
                        "UPDATE sessions SET revoked_at = COALESCE(revoked_at, ?) WHERE session_hash = ?",
                        (now, session_hash),
                    )
                    connection.execute("COMMIT")
                    return None, reason
                connection.execute(
                    "UPDATE sessions SET last_seen_at = ? WHERE session_hash = ?",
                    (now, session_hash),
                )
                connection.execute("COMMIT")
                return SessionContext(
                    subject=str(row["subject"]),
                    display_name=str(row["display_name"]),
                    source_role=str(row["source_role"]),
                    scopes=frozenset(json.loads(row["scopes_json"])),
                    issued_at=int(row["issued_at"]),
                    expires_at=int(row["expires_at"]),
                    last_seen_at=now,
                    authentication_event_id=str(row["authentication_event_id"]),
                    session_identifier_hash=session_hash,
                ), reason
        except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise AuthenticationError("session store is unavailable") from exc

    def revoke_session(self, session_hash: str, now: int) -> bool:
        try:
            with contextlib.closing(self._connect()) as connection:
                cursor = connection.execute(
                    "UPDATE sessions SET revoked_at = ? WHERE session_hash = ? AND revoked_at IS NULL",
                    (now, session_hash),
                )
                return cursor.rowcount == 1
        except sqlite3.Error as exc:
            raise AuthenticationError("session store is unavailable") from exc
