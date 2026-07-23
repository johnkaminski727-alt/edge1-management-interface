#!/usr/bin/env python3
"""SQLite persistence for the Telegraph Office reference service."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class TelegraphStore:
    """Small transactional store for peers, messages, receipts, and replay state."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self.lock = threading.RLock()
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self._initialize()

    def _initialize(self) -> None:
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS peers (
                    office_id TEXT PRIMARY KEY,
                    trust_status TEXT NOT NULL,
                    identity_json TEXT NOT NULL,
                    updated_at INTEGER NOT NULL,
                    identity_verified INTEGER NOT NULL CHECK(identity_verified IN (0, 1))
                );

                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    envelope_json TEXT NOT NULL,
                    accepted_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id TEXT PRIMARY KEY,
                    message_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    receipt_json TEXT NOT NULL,
                    recorded_at INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS receipts_message_sequence_idx
                    ON receipts(message_id, sequence);

                CREATE TABLE IF NOT EXISTS replay_nonces (
                    nonce TEXT PRIMARY KEY,
                    first_seen REAL NOT NULL
                );
                """
            )

    @staticmethod
    def _dump(value: dict[str, Any]) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _load(value: str) -> dict[str, Any]:
        document = json.loads(value)
        if not isinstance(document, dict):
            raise ValueError("stored Telegraph document is not an object")
        return document

    def save_peer(self, record: dict[str, Any]) -> None:
        with self.lock, self.connection:
            self.connection.execute(
                """
                INSERT INTO peers(office_id, trust_status, identity_json, updated_at, identity_verified)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(office_id) DO UPDATE SET
                    trust_status = excluded.trust_status,
                    identity_json = excluded.identity_json,
                    updated_at = excluded.updated_at,
                    identity_verified = excluded.identity_verified
                """,
                (
                    record["office_id"],
                    record["trust_status"],
                    self._dump(record["identity"]),
                    int(record["updated_at"]),
                    1 if record.get("identity_verified") else 0,
                ),
            )

    def load_peers(self) -> dict[str, dict[str, Any]]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT office_id, trust_status, identity_json, updated_at, identity_verified FROM peers"
            ).fetchall()
        return {
            row["office_id"]: {
                "office_id": row["office_id"],
                "trust_status": row["trust_status"],
                "identity": self._load(row["identity_json"]),
                "updated_at": row["updated_at"],
                "identity_verified": bool(row["identity_verified"]),
            }
            for row in rows
        }

    def save_message(self, envelope: dict[str, Any], accepted_at: int) -> None:
        with self.lock, self.connection:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO messages(message_id, origin, destination, envelope_json, accepted_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    envelope["message_id"],
                    envelope["origin"],
                    envelope["destination"],
                    self._dump(envelope),
                    accepted_at,
                ),
            )

    def load_messages(self) -> dict[str, dict[str, Any]]:
        with self.lock:
            rows = self.connection.execute("SELECT message_id, envelope_json FROM messages").fetchall()
        return {row["message_id"]: self._load(row["envelope_json"]) for row in rows}

    def save_receipt(self, receipt: dict[str, Any], recorded_at: int) -> None:
        with self.lock, self.connection:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO receipts(receipt_id, message_id, sequence, receipt_json, recorded_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    receipt["receipt_id"],
                    receipt["message_id"],
                    int(receipt.get("sequence", 0)),
                    self._dump(receipt),
                    recorded_at,
                ),
            )

    def load_receipts(self) -> dict[str, list[dict[str, Any]]]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT message_id, receipt_json FROM receipts ORDER BY message_id, sequence, recorded_at"
            ).fetchall()
        result: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            result.setdefault(row["message_id"], []).append(self._load(row["receipt_json"]))
        return result

    def accept_nonce(self, nonce: str, now: float, window_seconds: int) -> bool:
        cutoff = now - window_seconds
        with self.lock, self.connection:
            self.connection.execute("DELETE FROM replay_nonces WHERE first_seen < ?", (cutoff,))
            try:
                self.connection.execute(
                    "INSERT INTO replay_nonces(nonce, first_seen) VALUES (?, ?)",
                    (nonce, now),
                )
            except sqlite3.IntegrityError:
                return False
        return True

    def close(self) -> None:
        with self.lock:
            self.connection.close()

    def __enter__(self) -> "TelegraphStore":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
