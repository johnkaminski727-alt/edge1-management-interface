#!/usr/bin/env python3

import json
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

APPROVALS = (
    BASE /
    "data/registry/interconnect/approvals/carrier-approvals.json"
)

REGISTRY = (
    BASE /
    "data/registry/interconnect/interconnect-registry.json"
)


def main():

    if not APPROVALS.exists():

        print(
            "ERROR: approval records missing"
        )

        return 1


    with open(APPROVALS) as f:
        approvals = json.load(f)


    with open(REGISTRY) as f:
        registry = json.load(f)


    carriers = {
        c["id"]: c
        for c in registry.get(
            "carriers",
            []
        )
    }


    ok = True


    for approval in approvals.get(
        "approvals",
        []
    ):

        carrier_id = approval.get(
            "carrier_id"
        )

        if carrier_id not in carriers:

            print(
                f"ERROR: approval references missing carrier {carrier_id}"
            )

            ok = False


        if approval.get(
            "new_state"
        ) != "approved":

            print(
                f"ERROR: invalid approval state for {carrier_id}"
            )

            ok = False


    if ok:

        print(
            "Approval record validation passed"
        )

        print(
            f"approvals checked: {len(approvals.get('approvals', []))}"
        )

        return 0


    print(
        "Approval record validation failed"
    )

    return 1


if __name__ == "__main__":
    sys.exit(main())
