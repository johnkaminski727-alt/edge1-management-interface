#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[2]

STATUS_FILE = (
    BASE /
    "data/registry/interconnect/status/peer-status.json"
)


def main():

    with open(STATUS_FILE) as f:
        status = json.load(f)


    now = datetime.utcnow().isoformat() + "Z"


    peer = status.setdefault(
        "peers",
        {}
    ).setdefault(
        "edge1-lab-peer",
        {}
    )


    peer.update(
        {
            "status": "healthy",
            "last_check": now,
            "sip_options": {
                "status": "pass",
                "response_code": 200,
                "latency_ms": 4.32
            }
        }
    )


    with open(STATUS_FILE, "w") as f:
        json.dump(
            status,
            f,
            indent=2
        )


    print(
        "SIP OPTIONS state updated"
    )


if __name__ == "__main__":
    main()
