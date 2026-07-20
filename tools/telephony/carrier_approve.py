#!/usr/bin/env python3

import json
import sys
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[2]

REGISTRY = (
    BASE /
    "data/registry/interconnect/interconnect-registry.json"
)

APPROVALS = (
    BASE /
    "data/registry/interconnect/approvals/carrier-approvals.json"
)


def main():

    if len(sys.argv) < 2:
        print(
            "Usage: carrier_approve.py <carrier_id>"
        )
        return 1

    carrier_id = sys.argv[1]

    with open(REGISTRY) as f:
        registry = json.load(f)

    with open(APPROVALS) as f:
        approvals = json.load(f)


    carrier = None

    for item in registry.get("carriers", []):
        if item.get("id") == carrier_id:
            carrier = item
            break


    if carrier is None:
        print("Carrier not found")
        return 1


    current = carrier.get(
        "status",
        "planned"
    )


    if current != "testing":

        print(
            f"Approval blocked. Current state: {current}"
        )

        return 1


    carrier["status"] = "approved"


    approvals.setdefault(
        "approvals",
        []
    )

    approvals["approvals"].append(
        {
            "carrier_id": carrier_id,
            "previous_state": current,
            "new_state": "approved",
            "approved_at": datetime.utcnow().isoformat() + "Z",
            "approved_by": "operator"
        }
    )


    REGISTRY.write_text(
        json.dumps(
            registry,
            indent=2
        )
    )

    APPROVALS.write_text(
        json.dumps(
            approvals,
            indent=2
        )
    )


    print(
        "Carrier approved"
    )

    print(
        f"Previous: {current}"
    )

    print(
        "New: approved"
    )


if __name__ == "__main__":
    raise SystemExit(main())
