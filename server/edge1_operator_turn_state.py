#!/usr/bin/env python3
"""Deterministic SQLite-backed turn-ownership state for Fen/Gus/Edge1 coordination.

Turn state is keyed by (task_id, conversation_id). All mutating operations
commit turn_state, turn_audit, turn_outbox, and turn_idempotency changes in a
single SQLite transaction -- a true atomic multi-table commit, not
sequential best-effort writes. This uses only the Python standard library
(sqlite3); no new dependency.

Storage default: a durable per-user state directory under the home
directory, not system temp -- restart-persistent state must not default to
somewhere the OS is free to clear. Real production deployment should set
EDGE1_OPERATOR_TURN_STATE_ROOT explicitly to a dedicated, ops-provisioned
path; that is a deployment decision and out of scope for this spike.

Task/conversation creation is out of scope for this spike. status() and
handoff() only operate on already-seeded state; seed() exists for that
purpose and for tests, and is not exposed as an MCP tool.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Callable


class TurnStateError(Exception):
    """Base error for turn-state operations."""


class UnknownTurnError(TurnStateError):
    """Raised when a (task_id, conversation_id) pair has no existing turn state."""


class StaleEpochError(TurnStateError):
    """Raised when a handoff request's expected_epoch does not match current state."""


class UnauthorizedOwnerError(TurnStateError):
    """Raised when the requesting agent is not the current owner."""


class IdempotencyConflictError(TurnStateError):
    """Raised when an idempotency_key is reused with different request parameters.

    An exact replay (identical parameters) of an already-applied
    idempotency_key returns the cached result safely. Reusing the same key
    with different requesting_agent/to_agent/expected_epoch/reason/evidence
    is a caller bug or key collision, not a replay, and must not silently
    return stale cached data for a different request.
    """


_SCHEMA = """
CREATE TABLE IF NOT EXISTS turn_state (
    task_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    owner_agent TEXT NOT NULL,
    state TEXT NOT NULL,
    turn_epoch INTEGER NOT NULL,
    started_at REAL NOT NULL,
    last_activity_at REAL NOT NULL,
    handed_off_at REAL,
    previous_owner TEXT,
    handoff_reason TEXT,
    handoff_evidence TEXT,
    PRIMARY KEY (task_id, conversation_id)
);

CREATE TABLE IF NOT EXISTS turn_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    event TEXT NOT NULL,
    from_agent TEXT,
    to_agent TEXT,
    turn_epoch INTEGER NOT NULL,
    idempotency_key TEXT NOT NULL,
    execution_id TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS turn_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    delivered INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS turn_idempotency (
    task_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (task_id, conversation_id, idempotency_key)
);
"""


def _default_root() -> str:
    configured = os.environ.get("EDGE1_OPERATOR_TURN_STATE_ROOT")
    if configured:
        return configured
    # Durable per-user state dir, not system temp -- survives reboots and
    # requires no privileged setup. Production deployment should override
    # this via the env var above with a dedicated, ops-provisioned path.
    return str(Path.home() / ".local" / "state" / "edge1-operator-mcp" / "turn-state")


def _request_fingerprint(
    requesting_agent: str,
    to_agent: str,
    expected_epoch: int,
    reason: str | None,
    evidence: str | None,
) -> str:
    """Canonical representation of a handoff request's identity, used to tell
    an exact replay (same key, same params -- safe) apart from a reused key
    with different params (a conflict, not a replay)."""
    return json.dumps(
        {
            "requesting_agent": requesting_agent,
            "to_agent": to_agent,
            "expected_epoch": expected_epoch,
            "reason": reason,
            "evidence": evidence,
        },
        sort_keys=True,
    )


class TurnStateStore:
    def __init__(
        self,
        root: str | None = None,
        audit_writer: Callable[[str, dict], Any] | None = None,
        _fault_injector: Callable[[str], None] | None = None,
    ):
        self.root = Path(root or _default_root())
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "turn_state.sqlite3"
        # Optional legacy JSONL projection -- NOT authoritative, may lag or
        # be skipped entirely without affecting correctness.
        self._audit_writer = audit_writer
        # Test-only hook: called with a checkpoint name during handoff(); a
        # test can raise from it to force a mid-transaction rollback and
        # prove no partial rows survive. No-op in production.
        self._fault_injector = _fault_injector or (lambda checkpoint: None)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
        finally:
            conn.close()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        return {k: row[k] for k in row.keys()}

    def seed(self, task_id: str, conversation_id: str, owner_agent: str, state: str = "ACTIVE") -> dict:
        now = time.time()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO turn_state
                    (task_id, conversation_id, owner_agent, state, turn_epoch,
                     started_at, last_activity_at)
                VALUES (?, ?, ?, ?, 0, ?, ?)
                ON CONFLICT(task_id, conversation_id) DO UPDATE SET
                    owner_agent=excluded.owner_agent,
                    state=excluded.state,
                    turn_epoch=0,
                    started_at=excluded.started_at,
                    last_activity_at=excluded.last_activity_at,
                    handed_off_at=NULL,
                    previous_owner=NULL,
                    handoff_reason=NULL,
                    handoff_evidence=NULL
                """,
                (task_id, conversation_id, owner_agent, state, now, now),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.status(task_id, conversation_id)

    def status(self, task_id: str, conversation_id: str) -> dict:
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT * FROM turn_state WHERE task_id = ? AND conversation_id = ?",
                (task_id, conversation_id),
            )
            row = cur.fetchone()
        finally:
            conn.close()
        if row is None:
            raise UnknownTurnError(f"no turn state for {task_id}/{conversation_id}")
        return self._row_to_dict(row)

    def handoff(
        self,
        task_id: str,
        conversation_id: str,
        requesting_agent: str,
        to_agent: str,
        expected_epoch: int,
        idempotency_key: str,
        reason: str | None = None,
        evidence: str | None = None,
    ) -> dict:
        fingerprint = _request_fingerprint(requesting_agent, to_agent, expected_epoch, reason, evidence)

        conn = self._connect()
        result: dict | None = None
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._fault_injector("after_begin")

            cur = conn.execute(
                "SELECT * FROM turn_state WHERE task_id = ? AND conversation_id = ?",
                (task_id, conversation_id),
            )
            row = cur.fetchone()
            if row is None:
                raise UnknownTurnError(f"no turn state for {task_id}/{conversation_id}")
            current = self._row_to_dict(row)

            # Idempotency check before the epoch check: a legitimate replay
            # of an already-applied request must succeed even though the
            # epoch has since advanced past what the caller originally
            # expected. Only a genuinely new request can be stale.
            #
            # A replay is only "the same request" if its parameters match
            # what was stored under this key. If the key is reused with
            # different parameters, that is a conflict -- returning the old
            # cached result would silently apply a different request than
            # the one the caller actually sent.
            idem_row = conn.execute(
                """
                SELECT request_fingerprint, result_json FROM turn_idempotency
                WHERE task_id = ? AND conversation_id = ? AND idempotency_key = ?
                """,
                (task_id, conversation_id, idempotency_key),
            ).fetchone()
            if idem_row is not None:
                conn.rollback()
                if idem_row["request_fingerprint"] == fingerprint:
                    return json.loads(idem_row["result_json"])
                raise IdempotencyConflictError(
                    f"idempotency_key {idempotency_key!r} was already used for a "
                    "different request (different requesting_agent/to_agent/"
                    "expected_epoch/reason/evidence)"
                )

            if current["owner_agent"] != requesting_agent:
                raise UnauthorizedOwnerError(
                    f"{requesting_agent} is not the current owner ({current['owner_agent']})"
                )
            if current["turn_epoch"] != expected_epoch:
                raise StaleEpochError(
                    f"expected epoch {expected_epoch}, current epoch is {current['turn_epoch']}"
                )

            self._fault_injector("after_checks")

            now = time.time()
            new_epoch = current["turn_epoch"] + 1
            conn.execute(
                """
                UPDATE turn_state SET
                    previous_owner = owner_agent,
                    owner_agent = ?,
                    state = 'HANDED_OFF',
                    turn_epoch = ?,
                    last_activity_at = ?,
                    handed_off_at = ?,
                    handoff_reason = ?,
                    handoff_evidence = ?
                WHERE task_id = ? AND conversation_id = ?
                """,
                (to_agent, new_epoch, now, now, reason, evidence, task_id, conversation_id),
            )

            self._fault_injector("after_state_update")

            execution_id = uuid.uuid4().hex[:16]
            conn.execute(
                """
                INSERT INTO turn_audit
                    (task_id, conversation_id, event, from_agent, to_agent,
                     turn_epoch, idempotency_key, execution_id, created_at)
                VALUES (?, ?, 'turn.handed_off', ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id, conversation_id, current["owner_agent"], to_agent,
                    new_epoch, idempotency_key, execution_id, now,
                ),
            )

            self._fault_injector("after_audit_insert")

            cur = conn.execute(
                "SELECT * FROM turn_state WHERE task_id = ? AND conversation_id = ?",
                (task_id, conversation_id),
            )
            result = self._row_to_dict(cur.fetchone())
            outbox_payload = json.dumps(result, sort_keys=True)

            conn.execute(
                """
                INSERT INTO turn_outbox
                    (task_id, conversation_id, event_type, payload_json, created_at)
                VALUES (?, ?, 'turn.handed_off', ?, ?)
                """,
                (task_id, conversation_id, outbox_payload, now),
            )

            self._fault_injector("after_outbox_insert")

            conn.execute(
                """
                INSERT INTO turn_idempotency
                    (task_id, conversation_id, idempotency_key, request_fingerprint, result_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, conversation_id, idempotency_key, fingerprint, outbox_payload, now),
            )

            self._fault_injector("before_commit")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        if self._audit_writer is not None and result is not None:
            # Optional, non-authoritative projection into the legacy JSONL
            # audit convention. Best-effort: a failure here must not affect
            # the SQLite transaction already committed above.
            try:
                self._audit_writer(
                    str(self.root / "audit"),
                    {
                        "event": "turn.handed_off",
                        "task_id": task_id,
                        "conversation_id": conversation_id,
                        "from_agent": result["previous_owner"],
                        "to_agent": result["owner_agent"],
                        "turn_epoch": result["turn_epoch"],
                        "idempotency_key": idempotency_key,
                    },
                )
            except Exception:
                pass

        return result
