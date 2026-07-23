#!/usr/bin/env python3
"""Durable store-and-forward queue for Telegraph federation envelopes.

The queue persists encrypted envelopes without inspecting payload contents. It
supports bounded capacity, priority scheduling, exponential retry with jitter,
expiry, custody transfer, idempotent enqueue, and explicit terminal states.
"""

from __future__ import annotations

import hashlib
import json
import random
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from reference.telegraph_federation_demo import canonical_json


TERMINAL_STATES = {"delivered", "expired", "rejected", "cancelled"}
ACTIVE_STATES = {"queued", "retry_wait", "in_flight", "custody_transferred"}
PRIORITY_WEIGHT = {"emergency": 0, "urgent": 10, "normal": 20, "bulk": 30}


@dataclass(frozen=True)
class RetryPolicy:
    initial_seconds: int = 5
    maximum_seconds: int = 3600
    multiplier: float = 2.0
    jitter_fraction: float = 0.2
    max_attempts: int = 12

    def delay(self, attempt: int, rng: random.Random | None = None) -> int:
        if attempt < 1:
            raise ValueError("attempt must be positive")
        source = rng or random
        base = min(self.maximum_seconds, self.initial_seconds * (self.multiplier ** (attempt - 1)))
        jitter = base * self.jitter_fraction
        return max(1, int(round(source.uniform(base - jitter, base + jitter))))


@dataclass(frozen=True)
class QueueLimits:
    max_messages: int = 10000
    max_bytes: int = 512 * 1024 * 1024
    max_message_bytes: int = 16 * 1024 * 1024


class QueueFullError(RuntimeError):
    pass


class TelegraphStoreForwardQueue:
    def __init__(
        self,
        database: str | Path,
        office_id: str,
        retry_policy: RetryPolicy | None = None,
        limits: QueueLimits | None = None,
    ) -> None:
        self.database = str(database)
        self.office_id = office_id
        self.retry_policy = retry_policy or RetryPolicy()
        self.limits = limits or QueueLimits()
        self.connection = sqlite3.connect(self.database)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "TelegraphStoreForwardQueue":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS telegraph_queue (
                message_id TEXT PRIMARY KEY,
                destination TEXT NOT NULL,
                next_hop TEXT,
                priority TEXT NOT NULL,
                priority_weight INTEGER NOT NULL,
                envelope_json TEXT NOT NULL,
                envelope_digest TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                state TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                next_attempt_at INTEGER NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                lease_owner TEXT,
                lease_until INTEGER,
                custody_office TEXT,
                custody_receipt_json TEXT,
                delivered_at INTEGER,
                updated_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS telegraph_queue_due
              ON telegraph_queue(state, next_attempt_at, priority_weight, created_at);
            CREATE INDEX IF NOT EXISTS telegraph_queue_destination
              ON telegraph_queue(destination, state);
            CREATE TABLE IF NOT EXISTS telegraph_queue_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                event TEXT NOT NULL,
                recorded_at INTEGER NOT NULL,
                detail_json TEXT NOT NULL,
                FOREIGN KEY(message_id) REFERENCES telegraph_queue(message_id)
            );
            """
        )
        self.connection.commit()

    @staticmethod
    def _digest(envelope: dict[str, Any]) -> str:
        return "sha256:" + hashlib.sha256(canonical_json(envelope)).hexdigest()

    def _usage(self) -> tuple[int, int]:
        row = self.connection.execute(
            "SELECT COUNT(*) AS count, COALESCE(SUM(size_bytes), 0) AS bytes "
            "FROM telegraph_queue WHERE state NOT IN ('delivered','expired','rejected','cancelled')"
        ).fetchone()
        return int(row["count"]), int(row["bytes"])

    def _event(self, message_id: str, event: str, now: int, detail: dict[str, Any] | None = None) -> None:
        self.connection.execute(
            "INSERT INTO telegraph_queue_events(message_id,event,recorded_at,detail_json) VALUES(?,?,?,?)",
            (message_id, event, now, json.dumps(detail or {}, sort_keys=True, separators=(",", ":"))),
        )

    def enqueue(
        self,
        envelope: dict[str, Any],
        destination: str,
        expires_at: int,
        priority: str = "normal",
        next_hop: str | None = None,
        now: int | None = None,
    ) -> bool:
        timestamp = int(time.time()) if now is None else int(now)
        message_id = envelope.get("message_id")
        if not isinstance(message_id, str) or not message_id:
            raise ValueError("envelope message_id is required")
        if priority not in PRIORITY_WEIGHT:
            raise ValueError("invalid priority")
        if expires_at <= timestamp:
            raise ValueError("expires_at must be in the future")
        encoded = canonical_json(envelope).decode("utf-8")
        size_bytes = len(encoded.encode("utf-8"))
        if size_bytes > self.limits.max_message_bytes:
            raise QueueFullError("message exceeds max_message_bytes")
        existing = self.connection.execute(
            "SELECT envelope_digest FROM telegraph_queue WHERE message_id=?", (message_id,)
        ).fetchone()
        digest = self._digest(envelope)
        if existing is not None:
            if existing["envelope_digest"] != digest:
                raise ValueError("message_id collision with different envelope")
            return False
        count, used_bytes = self._usage()
        if count >= self.limits.max_messages or used_bytes + size_bytes > self.limits.max_bytes:
            raise QueueFullError("store-and-forward capacity exceeded")
        with self.connection:
            self.connection.execute(
                """INSERT INTO telegraph_queue(
                    message_id,destination,next_hop,priority,priority_weight,envelope_json,
                    envelope_digest,size_bytes,state,created_at,expires_at,next_attempt_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    message_id, destination, next_hop, priority, PRIORITY_WEIGHT[priority], encoded,
                    digest, size_bytes, "queued", timestamp, int(expires_at), timestamp, timestamp,
                ),
            )
            self._event(message_id, "accepted_for_custody", timestamp, {"office_id": self.office_id})
        return True

    def expire(self, now: int | None = None) -> int:
        timestamp = int(time.time()) if now is None else int(now)
        rows = self.connection.execute(
            "SELECT message_id FROM telegraph_queue WHERE state NOT IN ('delivered','expired','rejected','cancelled') AND expires_at<=?",
            (timestamp,),
        ).fetchall()
        with self.connection:
            for row in rows:
                self.connection.execute(
                    "UPDATE telegraph_queue SET state='expired',lease_owner=NULL,lease_until=NULL,updated_at=? WHERE message_id=?",
                    (timestamp, row["message_id"]),
                )
                self._event(row["message_id"], "expired", timestamp)
        return len(rows)

    def claim_due(
        self,
        worker_id: str,
        limit: int = 50,
        lease_seconds: int = 60,
        now: int | None = None,
    ) -> list[dict[str, Any]]:
        if limit < 1 or lease_seconds < 1:
            raise ValueError("limit and lease_seconds must be positive")
        timestamp = int(time.time()) if now is None else int(now)
        self.expire(timestamp)
        with self.connection:
            self.connection.execute(
                """UPDATE telegraph_queue SET state='retry_wait',lease_owner=NULL,lease_until=NULL,updated_at=?
                   WHERE state='in_flight' AND lease_until IS NOT NULL AND lease_until<=?""",
                (timestamp, timestamp),
            )
            rows = self.connection.execute(
                """SELECT * FROM telegraph_queue
                   WHERE state IN ('queued','retry_wait') AND next_attempt_at<=? AND expires_at>?
                   ORDER BY priority_weight ASC,next_attempt_at ASC,created_at ASC,message_id ASC LIMIT ?""",
                (timestamp, timestamp, limit),
            ).fetchall()
            claimed: list[dict[str, Any]] = []
            for row in rows:
                changed = self.connection.execute(
                    """UPDATE telegraph_queue SET state='in_flight',lease_owner=?,lease_until=?,updated_at=?
                       WHERE message_id=? AND state IN ('queued','retry_wait')""",
                    (worker_id, timestamp + lease_seconds, timestamp, row["message_id"]),
                ).rowcount
                if changed:
                    self._event(row["message_id"], "delivery_attempt_started", timestamp, {"worker_id": worker_id})
                    claimed.append({
                        "message_id": row["message_id"],
                        "destination": row["destination"],
                        "next_hop": row["next_hop"],
                        "priority": row["priority"],
                        "attempt_count": int(row["attempt_count"]),
                        "expires_at": int(row["expires_at"]),
                        "envelope": json.loads(row["envelope_json"]),
                    })
        return claimed

    def fail(
        self,
        message_id: str,
        worker_id: str,
        error: str,
        now: int | None = None,
        retryable: bool = True,
        rng: random.Random | None = None,
    ) -> str:
        timestamp = int(time.time()) if now is None else int(now)
        row = self.connection.execute(
            "SELECT * FROM telegraph_queue WHERE message_id=?", (message_id,)
        ).fetchone()
        if row is None:
            raise KeyError(message_id)
        if row["state"] != "in_flight" or row["lease_owner"] != worker_id:
            raise ValueError("worker does not own active lease")
        attempt = int(row["attempt_count"]) + 1
        expired = timestamp >= int(row["expires_at"])
        exhausted = attempt >= self.retry_policy.max_attempts
        if expired:
            state = "expired"
            next_attempt = timestamp
        elif not retryable or exhausted:
            state = "rejected"
            next_attempt = timestamp
        else:
            state = "retry_wait"
            next_attempt = timestamp + self.retry_policy.delay(attempt, rng=rng)
        with self.connection:
            self.connection.execute(
                """UPDATE telegraph_queue SET state=?,attempt_count=?,last_error=?,next_attempt_at=?,
                   lease_owner=NULL,lease_until=NULL,updated_at=? WHERE message_id=?""",
                (state, attempt, error[:1000], next_attempt, timestamp, message_id),
            )
            self._event(message_id, "delivery_failed", timestamp, {
                "attempt": attempt, "error": error[:1000], "retryable": retryable,
                "next_attempt_at": next_attempt if state == "retry_wait" else None,
                "terminal_state": state if state in TERMINAL_STATES else None,
            })
        return state

    def acknowledge_delivery(
        self,
        message_id: str,
        worker_id: str,
        receipt: dict[str, Any],
        now: int | None = None,
    ) -> None:
        timestamp = int(time.time()) if now is None else int(now)
        row = self.connection.execute(
            "SELECT state,lease_owner FROM telegraph_queue WHERE message_id=?", (message_id,)
        ).fetchone()
        if row is None:
            raise KeyError(message_id)
        if row["state"] != "in_flight" or row["lease_owner"] != worker_id:
            raise ValueError("worker does not own active lease")
        with self.connection:
            self.connection.execute(
                """UPDATE telegraph_queue SET state='delivered',delivered_at=?,custody_receipt_json=?,
                   lease_owner=NULL,lease_until=NULL,updated_at=? WHERE message_id=?""",
                (timestamp, json.dumps(receipt, sort_keys=True, separators=(",", ":")), timestamp, message_id),
            )
            self._event(message_id, "delivered", timestamp, {"receipt": receipt})

    def transfer_custody(
        self,
        message_id: str,
        worker_id: str,
        receiving_office: str,
        custody_receipt: dict[str, Any],
        now: int | None = None,
    ) -> None:
        timestamp = int(time.time()) if now is None else int(now)
        row = self.connection.execute(
            "SELECT state,lease_owner FROM telegraph_queue WHERE message_id=?", (message_id,)
        ).fetchone()
        if row is None:
            raise KeyError(message_id)
        if row["state"] != "in_flight" or row["lease_owner"] != worker_id:
            raise ValueError("worker does not own active lease")
        with self.connection:
            self.connection.execute(
                """UPDATE telegraph_queue SET state='custody_transferred',custody_office=?,custody_receipt_json=?,
                   lease_owner=NULL,lease_until=NULL,updated_at=? WHERE message_id=?""",
                (
                    receiving_office,
                    json.dumps(custody_receipt, sort_keys=True, separators=(",", ":")),
                    timestamp,
                    message_id,
                ),
            )
            self._event(message_id, "custody_transferred", timestamp, {
                "receiving_office": receiving_office, "receipt": custody_receipt,
            })

    def cancel(self, message_id: str, reason: str, now: int | None = None) -> bool:
        timestamp = int(time.time()) if now is None else int(now)
        with self.connection:
            row = self.connection.execute(
                "SELECT state FROM telegraph_queue WHERE message_id=?", (message_id,)
            ).fetchone()
            if row is None:
                raise KeyError(message_id)
            if row["state"] in TERMINAL_STATES or row["state"] == "custody_transferred":
                return False
            self.connection.execute(
                """UPDATE telegraph_queue SET state='cancelled',last_error=?,lease_owner=NULL,
                   lease_until=NULL,updated_at=? WHERE message_id=?""",
                (reason[:1000], timestamp, message_id),
            )
            self._event(message_id, "cancelled", timestamp, {"reason": reason[:1000]})
        return True

    def status(self, message_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM telegraph_queue WHERE message_id=?", (message_id,)
        ).fetchone()
        if row is None:
            raise KeyError(message_id)
        return {
            "message_id": row["message_id"],
            "destination": row["destination"],
            "next_hop": row["next_hop"],
            "priority": row["priority"],
            "state": row["state"],
            "attempt_count": int(row["attempt_count"]),
            "created_at": int(row["created_at"]),
            "expires_at": int(row["expires_at"]),
            "next_attempt_at": int(row["next_attempt_at"]),
            "last_error": row["last_error"],
            "custody_office": row["custody_office"],
            "delivered_at": row["delivered_at"],
        }

    def events(self, message_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT event,recorded_at,detail_json FROM telegraph_queue_events WHERE message_id=? ORDER BY event_id",
            (message_id,),
        ).fetchall()
        return [
            {"event": row["event"], "recorded_at": int(row["recorded_at"]), "detail": json.loads(row["detail_json"])}
            for row in rows
        ]

    def process_once(
        self,
        worker_id: str,
        sender: Callable[[dict[str, Any]], tuple[str, dict[str, Any]]],
        limit: int = 50,
        now: int | None = None,
    ) -> dict[str, int]:
        timestamp = int(time.time()) if now is None else int(now)
        counts = {"claimed": 0, "delivered": 0, "transferred": 0, "retry": 0, "rejected": 0}
        for item in self.claim_due(worker_id, limit=limit, now=timestamp):
            counts["claimed"] += 1
            try:
                outcome, receipt = sender(item)
                if outcome == "delivered":
                    self.acknowledge_delivery(item["message_id"], worker_id, receipt, now=timestamp)
                    counts["delivered"] += 1
                elif outcome == "custody_transferred":
                    receiving = receipt.get("office_id")
                    if not isinstance(receiving, str) or not receiving:
                        raise ValueError("custody receipt office_id is required")
                    self.transfer_custody(item["message_id"], worker_id, receiving, receipt, now=timestamp)
                    counts["transferred"] += 1
                else:
                    state = self.fail(item["message_id"], worker_id, f"unsupported outcome: {outcome}", now=timestamp, retryable=False)
                    counts["rejected" if state == "rejected" else "retry"] += 1
            except Exception as exc:
                state = self.fail(item["message_id"], worker_id, str(exc), now=timestamp, retryable=True)
                counts["retry" if state == "retry_wait" else "rejected"] += 1
        return counts
