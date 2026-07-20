#!/usr/bin/env python3

import json
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

REGISTRY = BASE / "data/registry/interconnect/interconnect-registry.json"


def main():

    with open(REGISTRY) as f:
        data = json.load(f)

    peers = {
        p["id"]
        for p in data.get("sip_peers", [])
    }

    ok = True
    priorities = {}

    for route in data.get("routing_rules", []):

        destination = route.get("destination")

        if destination not in peers:
            print(
                f"ERROR: Route {route.get('id')} "
                f"references missing peer {destination}"
            )
            ok = False

        priority = route.get("priority")

        if priority in priorities:
            print(
                f"ERROR: Duplicate route priority {priority}"
            )
            ok = False

        priorities[priority] = route.get("id")


    if ok:
        print("Routing policy validation passed")
        print(
            f"routes checked: "
            f"{len(data.get('routing_rules', []))}"
        )
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
