#!/usr/bin/env python3

import subprocess
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

GENERATOR = (
    BASE /
    "tools/telephony/generate_carrier_package.py"
)


def test_package_generation():

    result = subprocess.run(
        [
            "python3",
            str(GENERATOR),
            "lab-carrier-001"
        ],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0


    package = (
        BASE /
        "reports/carriers/lab-carrier-001"
    )


    assert (
        package /
        "carrier-profile.json"
    ).exists()

    assert (
        package /
        "validation-report.md"
    ).exists()


if __name__ == "__main__":

    test_package_generation()

    print(
        "carrier package tests passed"
    )
