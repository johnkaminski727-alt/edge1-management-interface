#!/usr/bin/env python3
"""Ingest local RFC822 files into the private WW.CX Mail Room correspondence store."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from mail_local_rfc822_source import ingest_rfc822_file, open_local_store


PRIVATE_ROOT = pathlib.Path("/var/lib/wwcx-mail-room")
DEFAULT_DB = PRIVATE_ROOT / "correspondence.sqlite3"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("messages", nargs="+", type=pathlib.Path)
    parser.add_argument("--db", type=pathlib.Path, default=DEFAULT_DB)
    parser.add_argument("--direction", choices=("inbound", "outbound"), default="inbound")
    return parser.parse_args()


def private_database_path(path: pathlib.Path) -> pathlib.Path:
    target = path.absolute()
    try:
        target.relative_to(PRIVATE_ROOT)
    except ValueError as exc:
        raise SystemExit("correspondence database must remain under /var/lib/wwcx-mail-room") from exc
    if target == PRIVATE_ROOT:
        raise SystemExit("correspondence database must be a file below the private root")
    return target


def main() -> int:
    args = parse_args()
    db_path = private_database_path(args.db)
    store = open_local_store(db_path)
    results = []
    for message_path in args.messages:
        projected = ingest_rfc822_file(message_path, store, direction=args.direction)
        results.append(
            {
                "message_id": projected["message_id"],
                "thread_id": projected["thread_id"],
                "occurred_at": projected["occurred_at"],
                "provenance": projected["provenance"],
                "content_is_untrusted": projected["content_is_untrusted"],
                "send_authorized": projected["send_authorized"],
                "mutation_authorized": projected["mutation_authorized"],
            }
        )
    print(
        json.dumps(
            {
                "contract": "wwcx.mail-local-intake-result.v1",
                "store_location": "private_mail_room_root",
                "count": len(results),
                "messages": results,
                "network_activity": False,
                "send_authorized": False,
                "mutation_authorized": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
