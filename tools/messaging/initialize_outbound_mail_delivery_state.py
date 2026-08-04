#!/usr/bin/env python3
"""Initialize and verify an empty outbound-mail delivery-state database.

The tool creates only the schema already defined by
`server/outbound_mail_delivery_events.py`. It never inserts an event, recipient,
suppression, credential, provider identifier, or message record.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sqlite3
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import outbound_mail_delivery_events as delivery_events


EXPECTED_TABLES = {"delivery_events", "recipient_delivery_state"}


def initialize(path: pathlib.Path) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = delivery_events._connect(path)  # repository-internal schema owner
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            if not str(row[0]).startswith("sqlite_")
        }
        event_count = int(
            connection.execute("SELECT COUNT(*) FROM delivery_events").fetchone()[0]
        )
        recipient_state_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM recipient_delivery_state"
            ).fetchone()[0]
        )
    finally:
        connection.close()
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    mode = path.stat().st_mode & 0o777
    if tables != EXPECTED_TABLES:
        raise RuntimeError(f"delivery-state tables mismatch: {sorted(tables)}")
    if event_count != 0 or recipient_state_count != 0:
        raise RuntimeError("delivery-state initialization found pre-existing records")
    if mode & 0o077:
        raise RuntimeError(f"delivery-state database mode is too broad: {mode:04o}")
    return {
        "database": str(path),
        "tables": sorted(tables),
        "event_count": event_count,
        "recipient_state_count": recipient_state_count,
        "mode": f"{mode:04o}",
        "synthetic_events_inserted": False,
        "recipient_data_inserted": False,
        "message_data_inserted": False,
        "credentials_inspected": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=pathlib.Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = initialize(args.database)
    except (OSError, sqlite3.Error, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
