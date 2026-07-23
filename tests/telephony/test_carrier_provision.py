#!/usr/bin/env python3

import json
import subprocess
from pathlib import Path


BASE = Path(__file__).resolve().parents[2]

PROVISION = (
    BASE /
    "tools/telephony/carrier_provision.py"
)


def test_carrier_provision():

    result = subprocess.run(
        [
            "python3",
            str(PROVISION),
            "test-carrier-001",
            "Test Carrier"
        ],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0

    record = (
        BASE /
        "data/registry/interconnect/provisioned/"
        "test-carrier-001.json"
    )

    assert record.exists()

    data = json.loads(
        record.read_text()
    )

    assert data["carrier_id"] == "test-carrier-001"


if __name__ == "__main__":

    test_carrier_provision()

    print(
        "carrier provisioning tests passed"
    )
