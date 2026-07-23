#!/usr/bin/env python3

import json
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

REGISTRY = (
    BASE /
    "data/registry/interconnect/interconnect-registry.json"
)


ALLOWED_STATES = {
    "planned",
    "testing",
    "validated",
    "approved",
    "active",
}


TRANSITIONS = {
    "planned": [
        "testing"
    ],
    "testing": [
        "validated"
    ],
    "validated": [
        "approved"
    ],
    "approved": [
        "active"
    ],
    "active": []
}


def main():

    with open(REGISTRY) as f:
        registry = json.load(f)


    ok = True


    for carrier in registry.get(
        "carriers",
        []
    ):

        status = carrier.get(
            "status",
            "planned"
        )


        print(
            f"{carrier['id']}: {status}"
        )


        if status not in ALLOWED_STATES:

            print(
                f"ERROR: invalid state {status}"
            )

            ok = False


    if ok:

        print(
            "Activation state validation passed"
        )

        return 0


    print(
        "Activation state validation failed"
    )

    return 1


if __name__ == "__main__":
    sys.exit(main())
