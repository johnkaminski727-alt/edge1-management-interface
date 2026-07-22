#!/usr/bin/env python3
"""Capture read-only telephony status snapshots into local analytics history.

This collector:
- reads existing telemetry only;
- stores sanitized snapshots only;
- has no PBX, carrier, routing, or configuration write path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from telephony_history import record_snapshot
from telephony_status_server import status_payload


def capture_snapshot(
    db_path: Path | None = None,
) -> dict[str, Any]:
    payload = status_payload()

    if db_path is None:
        record_snapshot(payload)
    else:
        record_snapshot(payload, db_path)

    return payload


if __name__ == "__main__":
    snapshot = capture_snapshot()
    print(snapshot["overall_status"])
