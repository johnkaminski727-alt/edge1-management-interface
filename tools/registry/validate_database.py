#!/usr/bin/env python3

import sqlite3
from pathlib import Path

DB = Path("data/telecom/numbering.db")

checks = [
    ("countries", "SELECT count(*) FROM countries"),
    ("calling_codes", "SELECT count(*) FROM calling_codes"),
    ("country_timezones", "SELECT count(*) FROM country_timezones"),
    ("nanpa_npa", "SELECT count(*) FROM nanpa_npa"),
]

with sqlite3.connect(DB) as db:

    print("Database validation")

    for name, query in checks:
        count = db.execute(query).fetchone()[0]
        print(f"{name}: {count}")

    errors = db.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

    print("sqlite integrity:", errors)

    if errors != "ok":
        raise SystemExit(1)

print("Database validation passed")
