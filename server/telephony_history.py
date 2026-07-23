#!/usr/bin/env python3
"""Append-only local history storage for sanitized telephony analytics snapshots.

This module stores analytics history only. It contains no PBX, SIP, carrier,
routing, credential, or configuration write capabilities.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_DB = Path("data/telephony/history/analytics-history.sqlite3")


def initialize(db_path: Path = DEFAULT_DB) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                overall_status TEXT NOT NULL,
                health_score INTEGER,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.commit()


def record_snapshot(
    payload: dict[str, Any],
    db_path: Path = DEFAULT_DB,
) -> None:
    initialize(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO snapshots (
                created_at,
                overall_status,
                health_score,
                payload_json
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                payload.get("generated_at", ""),
                payload.get("overall_status", "unknown"),
                payload.get("score"),
                json.dumps(payload, sort_keys=True),
            ),
        )
        conn.commit()


def latest_snapshot(
    db_path: Path = DEFAULT_DB,
) -> dict[str, Any] | None:
    initialize(db_path)

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT payload_json
            FROM snapshots
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    if not row:
        return None

    return json.loads(row[0])


def list_snapshots(
    db_path: Path = DEFAULT_DB,
    limit: int = 50,
) -> list[dict[str, Any]]:
    initialize(db_path)

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT payload_json
            FROM snapshots
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [json.loads(row[0]) for row in rows]
