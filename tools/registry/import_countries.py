#!/usr/bin/env python3

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "data/telecom/numbering.db"
SOURCE = ROOT / "data/registry/countries.json"


def utc():
    return datetime.now(timezone.utc).isoformat()


with sqlite3.connect(DB) as db:

    data = json.loads(SOURCE.read_text())

    db.execute("DELETE FROM countries")

    for country in data["countries"]:
        for code in country["calling_codes"]:
            db.execute(
                """
                INSERT INTO countries
                (
                    iso2,
                    iso3,
                    name,
                    calling_code
                )
                VALUES (?,?,?,?)
                """,
                (
                    country["iso_alpha2"],
                    country["iso_alpha3"],
                    country["name"],
                    code,
                )
            )

    db.execute(
        """
        INSERT OR REPLACE INTO registry_metadata
        (key,value)
        VALUES (?,?)
        """,
        (
            "countries_last_import",
            utc()
        )
    )

print("Country registry imported")
