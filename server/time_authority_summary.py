#!/usr/bin/env python3
"""Return a bounded Time Authority health summary."""

from __future__ import annotations

import json
from pathlib import Path


FIXTURE = Path(
    "modules/time-authority/fixtures/baseline-measurements.json"
)


def main() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    records = payload.get("records", [])

    observers = {
        str(item.get("observer_id"))
        for item in records
        if item.get("observer_id")
    }

    reachable = [
        item for item in records
        if item.get("reachable") is True
    ]

    total = len(records)
    reachable_count = len(reachable)

    result = {
        "status": (
            "healthy"
            if total > 0 and reachable_count == total
            else "degraded"
        ),
        "observer_count": len(observers),
        "source_count": len({
            str(item.get("source_id"))
            for item in records
            if item.get("source_id")
        }),
        "reachable_sources": reachable_count,
        "total_sources": total,
        "consensus": (
            "healthy"
            if total > 0 and reachable_count == total
            else "degraded"
        ),
    }

    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
