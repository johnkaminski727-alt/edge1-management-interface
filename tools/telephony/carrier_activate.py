#!/usr/bin/env python3

import json
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

REGISTRY = (
    BASE /
    "data/registry/interconnect/interconnect-registry.json"
)


ALLOWED_ACTIVATION = {
    "approved"
}


def main():

    if len(sys.argv) < 2:

        print(
            "Usage: carrier_activate.py <carrier_id>"
        )

        return 1


    carrier_id = sys.argv[1]


    with open(REGISTRY) as f:
        registry = json.load(f)


    found = None


    for carrier in registry.get(
        "carriers",
        []
    ):

        if carrier.get("id") == carrier_id:

            found = carrier
            break


    if not found:

        print(
            "Carrier not found"
        )

        return 1


    current = found.get(
        "status",
        "planned"
    )


    print(
        f"Carrier: {carrier_id}"
    )

    print(
        f"Current state: {current}"
    )


    if current not in ALLOWED_ACTIVATION:

        print()
        print(
            "Activation blocked"
        )

        print(
            "Carrier must be approved before activation"
        )

        return 1


    found["status"] = "active"


    REGISTRY.write_text(
        json.dumps(
            registry,
            indent=2
        )
    )


    print()
    print(
        "Carrier activated"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
