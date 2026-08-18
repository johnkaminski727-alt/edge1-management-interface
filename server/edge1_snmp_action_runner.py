#!/usr/bin/env python3
"""Execute a bounded batch of approved SNMP remediation proposals."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from edge1_snmp_actions import execute_proposal
from edge1_snmp_platform import connect_db, utcnow
from edge1_snmp_secure_exec import SecureNetSNMP
from edge1_snmp_services import ensure_extended_schema


def run_batch(conn, *, limit: int = 10) -> dict:
    limit = max(1, min(int(limit), 100))
    rows = conn.execute(
        "SELECT proposal_id FROM action_proposals WHERE state='approved' ORDER BY created_at LIMIT ?",
        (limit,),
    ).fetchall()
    results = []
    net = SecureNetSNMP()
    for row in rows:
        proposal_id = row["proposal_id"]
        try:
            result = execute_proposal(conn, proposal_id, net=net)
            results.append({"proposal_id": proposal_id, "state": result["state"]})
        except Exception as exc:
            results.append({"proposal_id": proposal_id, "state": "failed", "error_type": type(exc).__name__})
    return {"generated_at": utcnow(), "processed": len(results), "results": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("EDGE1_SNMP_DB", "/var/lib/edge1-snmp/snmp.sqlite3")))
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    conn = connect_db(args.db)
    try:
        ensure_extended_schema(conn)
        result = run_batch(conn, limit=args.limit)
    finally:
        conn.close()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
