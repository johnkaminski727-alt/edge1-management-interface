#!/usr/bin/env python3
"""Unified Contacts additive migration utility."""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from schema_v1 import migrate


EXPECTED_PHONES = 677


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = (
        "phone_numbers",
        "organizations",
        "associations",
        "evidence",
        "occurrences",
        "source_documents",
        "contact_entities",
        "contact_points",
        "contact_assertions",
        "provenance_records",
        "assertion_evidence",
        "contact_observations",
        "candidate_correlations",
        "rejected_extractions",
    )

    result = {}
    for table in tables:
        result[table] = conn.execute(
            f'SELECT COUNT(*) FROM "{table}"'
        ).fetchone()[0]
    return result


def validate(conn: sqlite3.Connection) -> None:
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()

    if integrity != "ok":
        raise RuntimeError(f"integrity_check failed: {integrity}")

    if fk:
        raise RuntimeError(
            f"foreign_key_check returned {len(fk)} error(s)"
        )


def dry_run(source: Path) -> None:
    with tempfile.TemporaryDirectory(
        prefix="edge1-unified-contacts-"
    ) as directory:
        target = Path(directory) / "dry-run.sqlite"
        shutil.copy2(source, target)

        with closing(sqlite3.connect(target)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")

            before_phones = conn.execute(
                "SELECT COUNT(*) FROM phone_numbers"
            ).fetchone()[0]

            migrate(conn)
            conn.commit()
            validate(conn)

            result = counts(conn)

            if before_phones != result["phone_numbers"]:
                raise RuntimeError(
                    "legacy phone count changed during additive migration"
                )

            print("mode: dry-run")
            print("integrity: ok")
            print("foreign_key_errors: 0")

            for key, value in result.items():
                print(f"{key}: {value}")

            print(
                "schema_version:",
                conn.execute(
                    """
                    SELECT value
                    FROM schema_metadata
                    WHERE key='unified_contacts_schema_version'
                    """
                ).fetchone()[0],
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="apply migration to supplied database",
    )
    args = parser.parse_args()

    if not args.database.is_file():
        parser.error("database does not exist")

    if not args.apply:
        dry_run(args.database)
        return 0

    with closing(sqlite3.connect(args.database)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        migrate(conn)
        conn.commit()
        validate(conn)

    print("mode: apply")
    print("migration: complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
