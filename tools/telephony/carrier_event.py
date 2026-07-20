#!/usr/bin/env python3

import json
import sys
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[2]

AUDIT = (
    BASE /
    "data/registry/interconnect/audit/carrier-events.json"
)


def main():

    if len(sys.argv) < 3:
        print("Usage: carrier_event.py <carrier_id> <event>")
        return 1

    carrier_id = sys.argv[1]
    event = sys.argv[2]

    data = {}

    if AUDIT.exists():
        data = json.loads(
            AUDIT.read_text()
        )

    data.setdefault(
        "events",
        []
    )

    data["events"].append(
        {
            "carrier_id": carrier_id,
            "event": event,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "operator": "operator"
        }
    )

    AUDIT.write_text(
        json.dumps(
            data,
            indent=2
        )
    )

    print(
        f"Recorded {event} for {carrier_id}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
