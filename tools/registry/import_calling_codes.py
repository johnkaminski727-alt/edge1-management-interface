#!/usr/bin/env python3

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "data/telecom/numbering.db"
SOURCE = ROOT / "data/registry/calling_codes.json"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS calling_codes (
            id INTEGER PRIMARY KEY,
            country TEXT NOT NULL,
            calling_code TEXT NOT NULL,
            region TEXT,
            status TEXT NOT NULL DEFAULT 'assigned'
        )
        """
    )

    columns = {
        row[1]
        for row in db.execute(
            "PRAGMA table_info(calling_codes)"
        ).fetchall()
    }

    if "status" not in columns:
        db.execute(
            """
            ALTER TABLE calling_codes
            ADD COLUMN status TEXT NOT NULL DEFAULT 'assigned'
            """
        )


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = data.get("calling_codes")

    if not isinstance(records, list):
        raise ValueError(
            "calling_codes.json must contain a calling_codes list"
        )

    with sqlite3.connect(DB) as db:
        ensure_schema(db)

        db.execute("DELETE FROM calling_codes")

        db.executemany(
            """
            INSERT INTO calling_codes
            (
                country,
                calling_code,
                region,
                status
            )
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    item["country"],
                    item["calling_code"],
                    item.get("region", ""),
                    item.get("status", "assigned"),
                )
                for item in records
            ],
        )

        db.execute(
            """
            INSERT OR REPLACE INTO registry_metadata
            (key, value)
            VALUES (?, ?)
            """,
            (
                "calling_codes_last_import",
                utc(),
            ),
        )

    print(f"Calling code registry imported: {len(records)}")


if __name__ == "__main__":
    main()
