#!/usr/bin/env python3

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "data/telecom/numbering.db"
SOURCE = ROOT / "data/registry/timezones.json"


def utc():
    return datetime.now(timezone.utc).isoformat()


with sqlite3.connect(DB) as db:

    data = json.loads(SOURCE.read_text())

    db.execute("DELETE FROM country_timezones")

    for tz in data["timezones"]:
        db.execute(
            """
            INSERT INTO country_timezones
            (
                country,
                timezone,
                dst_supported
            )
            VALUES (?,?,?)
            """,
            (
                tz["country"],
                tz["iana_name"],
                1 if tz.get("dst_supported") else 0,
            )
        )

    db.execute(
        """
        INSERT OR REPLACE INTO registry_metadata
        (key,value)
        VALUES (?,?)
        """,
        (
            "timezones_last_import",
            utc()
        )
    )

print("Timezone registry imported")
