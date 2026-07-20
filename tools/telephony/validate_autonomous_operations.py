#!/usr/bin/env python3

import json
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

FILES = [
    "data/registry/interconnect/autonomy/policies.json",
    "data/registry/interconnect/autonomy/actions.json",
    "data/registry/interconnect/autonomy/execution-history.json",
    "data/registry/interconnect/autonomy/rollback-history.json"
]


def main():

    for item in FILES:

        path = BASE / item

        if not path.exists():

            print(
                "Missing:",
                item
            )

            return 1

        json.loads(
            path.read_text()
        )


    print(
        "Autonomous operations validation passed"
    )

    print(
        f"records checked: {len(FILES)}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
