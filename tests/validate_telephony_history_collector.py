#!/usr/bin/env python3

import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.telephony_history import list_snapshots
from server.telephony_history_collector import capture_snapshot


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "history.sqlite3"

        payload = capture_snapshot(db)

        assert "generated_at" in payload
        assert "services" in payload
        assert "alerts" in payload

        snapshots = list_snapshots(db)

        assert len(snapshots) == 1
        assert snapshots[0]["generated_at"] == payload["generated_at"]

    print("telephony history collector validation passed")


if __name__ == "__main__":
    main()
