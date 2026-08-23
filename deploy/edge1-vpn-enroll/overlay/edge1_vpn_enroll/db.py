from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS invites (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  label TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  profile TEXT NOT NULL,
  max_uses INTEGER NOT NULL DEFAULT 1,
  uses INTEGER NOT NULL DEFAULT 0,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  created_by TEXT,
  revoked_at TEXT,
  owner_subject TEXT NOT NULL DEFAULT '',
  owner_display_name TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS devices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invite_id INTEGER NOT NULL REFERENCES invites(id),
  label TEXT NOT NULL,
  peer_public_key TEXT NOT NULL UNIQUE,
  address TEXT NOT NULL UNIQUE,
  profile TEXT NOT NULL,
  created_at TEXT NOT NULL,
  revoked_at TEXT,
  owner_subject TEXT NOT NULL DEFAULT '',
  owner_display_name TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  action TEXT NOT NULL,
  subject TEXT NOT NULL,
  details_json TEXT NOT NULL
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        for table in ("invites", "devices"):
            columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if "owner_subject" not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN owner_subject TEXT NOT NULL DEFAULT ''")
            if "owner_display_name" not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN owner_display_name TEXT NOT NULL DEFAULT ''")
        conn.commit()
    finally:
        conn.close()


def audit(conn: sqlite3.Connection, ts: str, action: str, subject: str, details: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO audit (ts, action, subject, details_json) VALUES (?, ?, ?, ?)",
        (ts, action, subject, json.dumps(details, sort_keys=True)),
    )
