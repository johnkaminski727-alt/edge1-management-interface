"""Edge1-owned replay, opaque-session, CSRF, rate-limit, and audit storage."""
from __future__ import annotations

import contextlib
import hmac
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
        forbidden = {"assertion", "token", "cookie", "password", "signature", "private_key", "csrf"}
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
    """Atomic replay, hashed session, CSRF, rate-limit, and action-guard storage."""

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
                    CREATE TABLE IF NOT EXISTS session_csrf (
                        session_hash TEXT PRIMARY KEY,
                        csrf_hash TEXT NOT NULL,
                        expires_at INTEGER NOT NULL,
                        FOREIGN KEY(session_hash) REFERENCES sessions(session_hash) ON DELETE CASCADE
                    );
                    CREATE TABLE IF NOT EXISTS http_rate_limits (
                        bucket_key TEXT PRIMARY KEY,
                        window_started_at INTEGER NOT NULL,
                        request_count INTEGER NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS action_guards (
                        session_hash TEXT NOT NULL,
                        action_id TEXT NOT NULL,
                        started_at INTEGER NOT NULL,
                        completed_at INTEGER,
                        PRIMARY KEY(session_hash, action_id),
                        FOREIGN KEY(session_hash) REFERENCES sessions(session_hash) ON DELETE CASCADE
                    );
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
                    connection.execute("DELETE FROM session_csrf WHERE session_hash = ?", (session_hash,))
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
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    "UPDATE sessions SET revoked_at = ? WHERE session_hash = ? AND revoked_at IS NULL",
                    (now, session_hash),
                )
                connection.execute("DELETE FROM session_csrf WHERE session_hash = ?", (session_hash,))
                connection.execute("COMMIT")
                return cursor.rowcount == 1
        except sqlite3.Error as exc:
            raise AuthenticationError("session store is unavailable") from exc

    def set_csrf(self, session_hash: str, csrf_hash: str, expires_at: int) -> None:
        try:
            with contextlib.closing(self._connect()) as connection:
                connection.execute(
                    """
                    INSERT INTO session_csrf(session_hash, csrf_hash, expires_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(session_hash) DO UPDATE SET
                        csrf_hash = excluded.csrf_hash,
                        expires_at = excluded.expires_at
                    """,
                    (session_hash, csrf_hash, expires_at),
                )
        except sqlite3.Error as exc:
            raise AuthenticationError("CSRF state could not be created") from exc

    def verify_csrf(self, session_hash: str, csrf_hash: str, now: int) -> bool:
        try:
            with contextlib.closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT csrf_hash, expires_at FROM session_csrf WHERE session_hash = ?",
                    (session_hash,),
                ).fetchone()
                return bool(
                    row is not None
                    and now < int(row["expires_at"])
                    and hmac.compare_digest(str(row["csrf_hash"]), csrf_hash)
                )
        except sqlite3.Error as exc:
            raise AuthenticationError("CSRF state is unavailable") from exc

    def allow_rate(self, bucket_key: str, now: int, *, limit: int, window_seconds: int) -> bool:
        try:
            with contextlib.closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT window_started_at, request_count FROM http_rate_limits WHERE bucket_key = ?",
                    (bucket_key,),
                ).fetchone()
                if row is None or now - int(row["window_started_at"]) >= window_seconds:
                    connection.execute(
                        """
                        INSERT INTO http_rate_limits(bucket_key, window_started_at, request_count)
                        VALUES (?, ?, 1)
                        ON CONFLICT(bucket_key) DO UPDATE SET
                            window_started_at = excluded.window_started_at,
                            request_count = 1
                        """,
                        (bucket_key, now),
                    )
                    connection.execute("COMMIT")
                    return True
                if int(row["request_count"]) >= limit:
                    connection.execute("ROLLBACK")
                    return False
                connection.execute(
                    "UPDATE http_rate_limits SET request_count = request_count + 1 WHERE bucket_key = ?",
                    (bucket_key,),
                )
                connection.execute("COMMIT")
                return True
        except sqlite3.Error as exc:
            raise AuthenticationError("rate-limit state is unavailable") from exc

    def begin_action(
        self,
        session_hash: str,
        action_id: str,
        now: int,
        *,
        inflight_timeout_seconds: int,
        cooldown_seconds: int,
    ) -> str:
        try:
            with contextlib.closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT started_at, completed_at FROM action_guards WHERE session_hash = ? AND action_id = ?",
                    (session_hash, action_id),
                ).fetchone()
                if row is not None:
                    completed_at = row["completed_at"]
                    if completed_at is None and now - int(row["started_at"]) < inflight_timeout_seconds:
                        connection.execute("ROLLBACK")
                        return "in_progress"
                    if completed_at is not None and now - int(completed_at) < cooldown_seconds:
                        connection.execute("ROLLBACK")
                        return "cooldown"
                connection.execute(
                    """
                    INSERT INTO action_guards(session_hash, action_id, started_at, completed_at)
                    VALUES (?, ?, ?, NULL)
                    ON CONFLICT(session_hash, action_id) DO UPDATE SET
                        started_at = excluded.started_at,
                        completed_at = NULL
                    """,
                    (session_hash, action_id, now),
                )
                connection.execute("COMMIT")
                return "started"
        except sqlite3.Error as exc:
            raise AuthenticationError("action guard is unavailable") from exc

    def finish_action(self, session_hash: str, action_id: str, now: int) -> None:
        try:
            with contextlib.closing(self._connect()) as connection:
                connection.execute(
                    "UPDATE action_guards SET completed_at = ? WHERE session_hash = ? AND action_id = ?",
                    (now, session_hash, action_id),
                )
        except sqlite3.Error as exc:
            raise AuthenticationError("action guard is unavailable") from exc
