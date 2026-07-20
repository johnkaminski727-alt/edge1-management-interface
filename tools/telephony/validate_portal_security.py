#!/usr/bin/env python3

import json
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

POLICY = (
    BASE /
    "config/portal/hmac-policy.json"
)


def main():

    if not POLICY.exists():

        print(
            "Portal security policy missing"
        )

        return 1


    policy = json.loads(
        POLICY.read_text()
    )


    required = [
        "enabled",
        "algorithm",
        "allowed_clients"
    ]


    for item in required:

        if item not in policy:

            print(
                "Missing:",
                item
            )

            return 1


    print(
        "Portal security validation passed"
    )

    print(
        f"clients configured: {len(policy['allowed_clients'])}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
