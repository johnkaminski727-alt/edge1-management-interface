#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]


STEPS = [
    [
        "python3",
        "tools/telephony/import_provisioned_carrier.py"
    ],
    [
        "python3",
        "tools/telephony/validate_interconnect_registry.py"
    ],
    [
        "python3",
        "tools/telephony/validate_carrier_provision.py"
    ],
    [
        "python3",
        "tools/telephony/generate_sip_config.py"
    ],
    [
        "python3",
        "tools/telephony/generate_carrier_package.py"
    ]
]


def main():

    if len(sys.argv) < 2:
        print(
            "Usage: carrier_onboard.py <carrier_id>"
        )
        return 1


    carrier_id = sys.argv[1]


    print(
        "=== CARRIER ONBOARDING ==="
    )

    print()


    for step in STEPS:

        command = step + [carrier_id]

        print(
            "[RUN]",
            " ".join(command)
        )

        result = subprocess.run(
            command,
            cwd=BASE
        )

        if result.returncode != 0:

            print(
                "[FAIL]",
                " ".join(command)
            )

            return 1


        print(
            "[PASS]"
        )

        print()


    print(
        "Carrier onboarding complete"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
