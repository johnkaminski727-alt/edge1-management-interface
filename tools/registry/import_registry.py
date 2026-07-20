#!/usr/bin/env python3

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "data" / "telecom" / "numbering.db"
COUNTRIES = ROOT / "data" / "registry" / "countries.json"
TIMEZONES = ROOT / "data" / "registry" / "timezones.json"


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def import_countries():

    data = json.loads(COUNTRIES.read_text())

    with connect() as conn:
        conn.execute("DELETE FROM countries")

        for c in data["countries"]:

            for code in c["calling_codes"]:

                conn.execute(
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
                        c["iso_alpha2"],
                        c["iso_alpha3"],
                        c["name"],
                        code,
                    )
                )


def main():

    import_countries()

    with connect() as conn:
        print("Countries:",
              conn.execute(
                  "SELECT count(*) FROM countries"
              ).fetchone()[0])


if __name__ == "__main__":
    main()
