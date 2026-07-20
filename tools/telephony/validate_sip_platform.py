#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]


COMMANDS = [
    [
        "python3",
        "tools/telephony/validate_interconnect_registry.py"
    ],
    [
        "python3",
        "tools/telephony/validate_routing_policy.py"
    ],
    [
        "python3",
        "tools/telephony/sip_peer_health_check.py"
    ],
    [
        "python3",
        "tools/telephony/validate_peer_health_state.py"
    ],
    [
        "python3",
        "tools/telephony/generate_sip_config.py"
    ],
    [
        "python3",
        "tools/telephony/adapters/kamailio_adapter.py"
    ]
]


def main():

    print("=== EDGE1 SIP PLATFORM VALIDATION ===")
    print()

    for command in COMMANDS:

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

        print("[PASS]")
        print()


    print(
        "SIP platform validation complete"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
