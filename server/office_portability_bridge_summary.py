#!/usr/bin/env python3
"""Produce a privacy-preserving aggregate snapshot for Ava Office and Number Portability.

This module is intentionally read-only. It never returns work-item titles/outcomes,
proposal parameters, telephone numbers, customer references, document references, or
other record-level content. It is suitable for inclusion in the existing signed
Edge1 -> Business159 operations snapshot.

Keep this helper importable by the shared Operations Center collector's Python 3.6
compatibility check. Newer application services may use newer language features; this
small bridge deliberately does not.
"""

import argparse
import datetime as dt
import json
import os
import sqlite3
from pathlib import Path

DEFAULT_AVA_DB = Path("/var/lib/wwcx-ava-office-manager/office-manager.sqlite3")
DEFAULT_PORT_DB = Path("/var/lib/wwcx-portability/portability.sqlite3")


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def connect_ro(path):
    conn = sqlite3.connect("file:" + str(path.resolve()) + "?mode=ro", uri=True, timeout=3)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def ava_summary(path):
    if not path.is_file():
        return {"available": False, "mode": "read-only", "execution_enabled": False}
    try:
        with connect_ro(path) as conn:
            work = {str(row["state"]): int(row["count"]) for row in conn.execute("SELECT state,COUNT(*) AS count FROM work_items GROUP BY state")}
            actions = {str(row["status"]): int(row["count"]) for row in conn.execute("SELECT status,COUNT(*) AS count FROM action_proposals GROUP BY status")}
            instructions = int(conn.execute("SELECT COUNT(*) FROM standing_instructions WHERE enabled=1").fetchone()[0])
        return {
            "available": True,
            "mode": "read-only",
            "execution_enabled": False,
            "autonomy_level": "gated",
            "work_items": work,
            "actions": actions,
            "standing_instructions": instructions,
        }
    except sqlite3.Error:
        return {"available": False, "mode": "read-only", "execution_enabled": False, "error": "database_unavailable"}


def portability_summary(path):
    if not path.is_file():
        return {"available": False, "mode": "read-only", "submission_authorized": False, "cutover_authorized": False}
    try:
        with connect_ro(path) as conn:
            cases = {str(row["state"]): int(row["count"]) for row in conn.execute("SELECT state,COUNT(*) AS count FROM port_cases GROUP BY state")}
            numbers = int(conn.execute("SELECT COUNT(*) FROM port_numbers").fetchone()[0])
            documents = int(conn.execute("SELECT COUNT(*) FROM port_documents").fetchone()[0])
            flags = conn.execute("SELECT COALESCE(MAX(submission_authorized),0),COALESCE(MAX(cutover_authorized),0) FROM port_cases").fetchone()
        return {
            "available": True,
            "mode": "read-only",
            "cases": cases,
            "numbers": numbers,
            "documents": documents,
            "submission_authorized": bool(flags[0]),
            "cutover_authorized": bool(flags[1]),
        }
    except sqlite3.Error:
        return {"available": False, "mode": "read-only", "submission_authorized": False, "cutover_authorized": False, "error": "database_unavailable"}


def build_summary(ava_db=DEFAULT_AVA_DB, port_db=DEFAULT_PORT_DB):
    return {
        "format": "wwcx-office-services-summary-v1",
        "generated_at": utc_now(),
        "ava_office": ava_summary(ava_db),
        "number_portability": portability_summary(port_db),
        "privacy": {
            "record_level_content_included": False,
            "telephone_numbers_included": False,
            "transcripts_or_audio_included": False,
            "document_references_included": False,
            "credentials_included": False,
        },
    }


def write_atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(encoded)
    os.chmod(str(tmp), 0o600)
    os.replace(str(tmp), str(path))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ava-database", type=Path, default=DEFAULT_AVA_DB)
    parser.add_argument("--portability-database", type=Path, default=DEFAULT_PORT_DB)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = build_summary(args.ava_database, args.portability_database)
    if args.output:
        write_atomic(args.output, payload)
    else:
        print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
