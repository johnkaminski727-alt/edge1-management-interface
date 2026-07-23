#!/usr/bin/env python3

import json
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

POLICY = (
    BASE /
    "data/registry/interconnect/security/"
    "sip-security-policy.json"
)


def main():

    if not POLICY.exists():

        print(
            "ERROR: security policy missing"
        )

        return 1


    with open(POLICY) as f:
        policy = json.load(f)


    required = [
        "signaling",
        "network",
        "authentication",
        "compliance"
    ]


    for item in required:

        if item not in policy:

            print(
                f"ERROR: missing section {item}"
            )

            return 1


    print(
        "Security readiness validation passed"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
