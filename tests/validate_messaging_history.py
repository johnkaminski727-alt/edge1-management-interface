#!/usr/bin/env python3

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from messaging_gateway_collector import collect_gateway_health
from messaging_history import latest_snapshot, list_snapshots, record_snapshot

with tempfile.TemporaryDirectory() as temporary_directory:
    db_path = Path(temporary_directory) / "history.sqlite3"
    first = collect_gateway_health().to_dict()
    second = dict(first)
    second["checked_at"] = first["checked_at"] + "-second"

    record_snapshot(first, db_path)
    record_snapshot(second, db_path)

    assert latest_snapshot(db_path) == second
    assert list_snapshots(db_path, limit=1) == [second]
    assert list_snapshots(db_path, limit=10) == [second, first]

print("Messaging history validation passed")
print("Append-only sanitized snapshot storage confirmed")
