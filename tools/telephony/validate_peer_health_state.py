#!/usr/bin/env python3

import json
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

STATUS_FILE = (
    BASE /
    "data/registry/interconnect/status/peer-status.json"
)


def main():

    if not STATUS_FILE.exists():
        print("ERROR: missing peer health state")
        return 1

    with open(STATUS_FILE) as f:
        data = json.load(f)


    peers = data.get("peers", {})

    for peer, state in peers.items():

        if state.get("status") not in {
            "healthy",
            "degraded",
            "failed"
        }:
            print(
                f"ERROR: invalid status for {peer}"
            )
            return 1


    print("Peer health state validation passed")
    print(
        f"peers checked: {len(peers)}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
