#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parents[2]

REGISTRY = (
    BASE /
    "data/registry/interconnect/interconnect-registry.json"
)

OUTPUT = (
    BASE /
    "data/registry/interconnect/portal"
)


def main():

    registry = json.loads(
        REGISTRY.read_text()
    )


    carriers = []

    for carrier in registry.get(
        "carriers",
        []
    ):

        carriers.append(
            {
                "id": carrier.get("id"),
                "name": carrier.get("name"),
                "status": carrier.get("status")
            }
        )


    (OUTPUT / "carrier-status.json").write_text(
        json.dumps(
            {
                "generated":
                    datetime.utcnow().isoformat() + "Z",
                "carriers": carriers
            },
            indent=2
        )
    )


    (OUTPUT / "public-summary.json").write_text(
        json.dumps(
            {
                "platform":
                    "Edge1 SIP Interconnect",
                "status":
                    "operational",
                "generated":
                    datetime.utcnow().isoformat() + "Z"
            },
            indent=2
        )
    )


    print(
        "Portal export generated"
    )

    print(
        f"carriers exported: {len(carriers)}"
    )


if __name__ == "__main__":
    main()
