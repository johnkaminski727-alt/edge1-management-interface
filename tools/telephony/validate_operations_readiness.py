#!/usr/bin/env python3

import json
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

FILES = [
    "data/registry/interconnect/monitoring/thresholds.json",
    "data/registry/interconnect/monitoring/uptime-history.json",
    "data/registry/interconnect/routing/carrier-groups.json",
    "data/registry/interconnect/routing/failover-policy.json",
    "data/registry/interconnect/operations/incidents.json",
    "data/registry/interconnect/operations/maintenance.json",
    "data/registry/interconnect/operations/sla-records.json",
    "data/registry/interconnect/security/certificates.json"
]


def main():

    missing = []

    for item in FILES:

        path = BASE / item

        if not path.exists():

            missing.append(item)

        else:

            json.loads(
                path.read_text()
            )


    if missing:

        print(
            "Missing files:"
        )

        for item in missing:
            print(item)

        return 1


    print(
        "Operations readiness validation passed"
    )

    print(
        f"records checked: {len(FILES)}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
