#!/usr/bin/env python3

import json
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

REGISTRY = (
    BASE /
    "data/registry/interconnect/interconnect-registry.json"
)


def main():

    carrier_id = sys.argv[1]

    registry = json.loads(
        REGISTRY.read_text()
    )

    for carrier in registry["carriers"]:
        if carrier["id"] == carrier_id:
            carrier["status"] = "testing"
            REGISTRY.write_text(
                json.dumps(registry, indent=2)
            )
            print("Carrier rolled back")
            return 0

    print("Carrier not found")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
