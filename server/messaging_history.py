#!/usr/bin/env python3
"""Append-only SQLite history for sanitized messaging health snapshots."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("data/messaging/history/messaging-history.sqlite3")


def initialize(db_path: Path = DEFAULT_DB) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checked_at TEXT NOT NULL,
                gateway TEXT NOT NULL,
                state TEXT NOT NULL,
                service_active INTEGER NOT NULL,
                listener_reachable INTEGER NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.commit()


def record_snapshot(payload: dict[str, Any], db_path: Path = DEFAULT_DB) -> None:
    initialize(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO snapshots (
                checked_at, gateway, state, service_active,
                listener_reachable, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("checked_at", ""),
                payload.get("gateway", "wwcx-messaging-gateway"),
                payload.get("state", "unknown"),
                int(bool(payload.get("service_active"))),
                int(bool(payload.get("listener_reachable"))),
                json.dumps(payload, sort_keys=True),
            ),
        )
        conn.commit()


def latest_snapshot(db_path: Path = DEFAULT_DB) -> dict[str, Any] | None:
    initialize(db_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT payload_json FROM snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return json.loads(row[0]) if row else None


def list_snapshots(db_path: Path = DEFAULT_DB, limit: int = 50) -> list[dict[str, Any]]:
    initialize(db_path)
    safe_limit = max(1, min(int(limit), 500))
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT payload_json FROM snapshots ORDER BY id DESC LIMIT ?",
            (safe_limit,),
        ).fetchall()
    return [json.loads(row[0]) for row in rows]
