#!/usr/bin/env python3

import csv
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

DB = ROOT / "data/telecom/numbering.db"


def utc():
    return datetime.now(timezone.utc).isoformat()


def import_nanpa(csv_file: Path):

    imported = 0

    with sqlite3.connect(DB) as db:

        db.execute("DELETE FROM nanpa_npa")

        with csv_file.open(newline="") as handle:

            reader = csv.DictReader(handle)

            for row in reader:

                db.execute(
                    """
                    INSERT INTO nanpa_npa
                    (
                        npa,
                        country,
                        region,
                        state,
                        timezone,
                        status
                    )
                    VALUES (?,?,?,?,?,?)
                    """,
                    (
                        row["npa"],
                        row["country"],
                        row.get("region", ""),
                        row.get("state", ""),
                        row.get("timezone", ""),
                        row.get("status", "active"),
                    )
                )

                imported += 1

        db.execute(
            """
            INSERT OR REPLACE INTO registry_metadata
            (key,value)
            VALUES (?,?)
            """,
            (
                "nanpa_last_import",
                utc()
            )
        )

    return imported


if __name__ == "__main__":

    source = ROOT / "data/registry/nanpa_npa.csv"

    if not source.exists():
        raise SystemExit(
            f"Missing source file: {source}"
        )

    count = import_nanpa(source)

    print(
        f"NANPA imported: {count}"
    )
