#!/usr/bin/env python3

import json
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

REGISTRY = (
    BASE /
    "data/registry/interconnect/interconnect-registry.json"
)

PROVISIONED = (
    BASE /
    "data/registry/interconnect/provisioned"
)


def main():

    if len(sys.argv) < 2:
        print(
            "Usage: import_provisioned_carrier.py <carrier_id>"
        )
        return 1


    carrier_id = sys.argv[1]

    source = (
        PROVISIONED /
        f"{carrier_id}.json"
    )

    if not source.exists():
        print(
            "Provisioned carrier not found"
        )
        return 1


    carrier = json.loads(
        source.read_text()
    )

    registry = json.loads(
        REGISTRY.read_text()
    )


    registry.setdefault(
        "carriers",
        []
    )

    registry.setdefault(
        "sip_peers",
        []
    )


    if not any(
        c.get("id") == carrier_id
        for c in registry["carriers"]
    ):

        registry["carriers"].append(
            {
                "id": carrier_id,
                "name": carrier["name"],
                "status": carrier["status"],
                "contacts": []
            }
        )


    peer_id = carrier["sip"]["peer_id"]


    if not any(
        p.get("id") == peer_id
        for p in registry["sip_peers"]
    ):

        registry["sip_peers"].append(
            {
                "id": peer_id,
                "carrier_id": carrier_id,
                "endpoint": "pending",
                "transport": carrier["sip"]["transport"],
                "codecs": carrier["sip"]["codecs"],
                "health_check": "options"
            }
        )


    REGISTRY.write_text(
        json.dumps(
            registry,
            indent=2
        )
    )


    print(
        "Provisioned carrier imported"
    )


if __name__ == "__main__":
    raise SystemExit(main())
