#!/usr/bin/env python3

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "data/telecom/numbering.db"
SOURCE = ROOT / "data/registry/calling_codes.json"


def utc():
    return datetime.now(timezone.utc).isoformat()


with sqlite3.connect(DB) as db:

    data = json.loads(SOURCE.read_text())

    db.execute("""
    CREATE TABLE IF NOT EXISTS calling_codes (
        id INTEGER PRIMARY KEY,
        country TEXT NOT NULL,
        calling_code TEXT NOT NULL,
        region TEXT
    )
    """)

    db.execute("DELETE FROM calling_codes")

    for item in data["calling_codes"]:

        db.execute(
            """
            INSERT INTO calling_codes
            (
                country,
                calling_code,
                region
            )
            VALUES (?,?,?)
            """,
            (
                item["country"],
                item["calling_code"],
                item.get("region", "")
            )
        )

    db.execute(
        """
        INSERT OR REPLACE INTO registry_metadata
        (key,value)
        VALUES (?,?)
        """,
        (
            "calling_codes_last_import",
            utc()
        )
    )

print("Calling code registry imported")
