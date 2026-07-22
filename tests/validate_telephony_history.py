#!/usr/bin/env python3

import tempfile
from pathlib import Path

from server.telephony_history import (
    initialize,
    latest_snapshot,
    list_snapshots,
    record_snapshot,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "history.sqlite3"

        initialize(db)

        payload = {
            "generated_at": "2026-07-22T00:00:00Z",
            "overall_status": "healthy",
            "score": 100,
        }

        record_snapshot(payload, db)

        assert latest_snapshot(db)["overall_status"] == "healthy"
        assert len(list_snapshots(db)) == 1

    print("telephony history validation passed")


if __name__ == "__main__":
    main()
