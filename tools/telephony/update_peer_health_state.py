#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[2]

STATUS_FILE = (
    BASE /
    "data/registry/interconnect/status/peer-status.json"
)

HISTORY_FILE = (
    BASE /
    "data/registry/interconnect/status/health-history.json"
)


def load(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)

    return {}


def save(path, data):
    with open(path, "w") as f:
        json.dump(
            data,
            f,
            indent=2
        )


def main():

    status = load(STATUS_FILE)
    history = load(HISTORY_FILE)

    now = datetime.utcnow().isoformat() + "Z"

    check = {
        "peer": "edge1-lab-peer",
        "status": "healthy",
        "check": "reachability",
        "timestamp": now
    }

    status.setdefault("peers", {})

    status["peers"]["edge1-lab-peer"] = {
        "status": "healthy",
        "last_check": now
    }

    history.setdefault("checks", [])

    history["checks"].append(check)

    save(STATUS_FILE, status)
    save(HISTORY_FILE, history)

    print("Peer health state updated")


if __name__ == "__main__":
    main()
