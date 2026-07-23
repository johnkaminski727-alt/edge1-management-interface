#!/usr/bin/env python3

import subprocess
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

ONBOARD = (
    BASE /
    "tools/telephony/carrier_onboard.py"
)


def test_carrier_onboarding():

    result = subprocess.run(
        [
            "python3",
            str(ONBOARD),
            "lab-carrier-001"
        ],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0

    assert (
        "Carrier onboarding complete"
        in result.stdout
    )


if __name__ == "__main__":

    test_carrier_onboarding()

    print(
        "carrier onboarding tests passed"
    )
