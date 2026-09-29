#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from schema_v1 import migrate
from legacy_bridge import bridge_legacy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(
        prefix="edge1-contacts-bridge-"
    ) as directory:
        copy = Path(directory) / "bridge.sqlite"
        shutil.copy2(args.database, copy)

        with closing(sqlite3.connect(copy)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")

            legacy_before = {
                "phones": conn.execute(
                    "SELECT COUNT(*) FROM phone_numbers"
                ).fetchone()[0],
                "organizations": conn.execute(
                    "SELECT COUNT(*) FROM organizations"
                ).fetchone()[0],
                "associations": conn.execute(
                    "SELECT COUNT(*) FROM associations"
                ).fetchone()[0],
            }

            migrate(conn)
            stats = bridge_legacy(conn)
            conn.commit()

            integrity = conn.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

            fk = conn.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            entities = conn.execute(
                "SELECT COUNT(*) FROM contact_entities"
            ).fetchone()[0]

            points = conn.execute(
                "SELECT COUNT(*) FROM contact_points"
            ).fetchone()[0]

            assertions = conn.execute(
                "SELECT COUNT(*) FROM contact_assertions"
            ).fetchone()[0]

            unresolved_assertions = conn.execute("""
                SELECT COUNT(*)
                FROM contact_assertions AS ca
                JOIN contact_points AS cp
                  ON cp.id = ca.contact_point_id
                JOIN phone_numbers AS pn
                  ON pn.id = cp.legacy_phone_number_id
                JOIN associations AS a
                  ON a.phone_number_id = pn.id
                WHERE a.confidence = 'unresolved'
            """).fetchone()[0]

            print("mode: legacy-bridge-dry-run")

            for key, value in legacy_before.items():
                print(f"legacy_{key}: {value}")

            for key, value in stats.items():
                print(f"{key}: {value}")

            print(f"contact_entities: {entities}")
            print(f"contact_points: {points}")
            print(f"contact_assertions: {assertions}")
            print(
                "unresolved_identity_assertions:",
                unresolved_assertions,
            )
            print("integrity:", integrity)
            print("foreign_key_errors:", len(fk))

            if integrity != "ok":
                raise SystemExit("integrity failure")

            if fk:
                raise SystemExit("foreign key failure")

            if unresolved_assertions:
                raise SystemExit(
                    "unsafe unresolved identity assertion detected"
                )

            if entities != legacy_before["organizations"]:
                raise SystemExit(
                    "organization bridge count mismatch"
                )

            if points != legacy_before["phones"]:
                raise SystemExit(
                    "phone bridge count mismatch"
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
