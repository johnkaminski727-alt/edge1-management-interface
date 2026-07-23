#!/usr/bin/env python3

from pathlib import Path
import subprocess


BASE = Path(__file__).resolve().parents[2]

ADAPTER = (
    BASE /
    "tools/telephony/adapters/"
    "kamailio_adapter.py"
)

OUTPUT = (
    BASE /
    "generated/telephony/kamailio"
)


def test_kamailio_adapter_runs():

    result = subprocess.run(
        ["python3", str(ADAPTER)],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0


def test_kamailio_output_exists():

    assert (
        OUTPUT /
        "kamailio-peers.cfg"
    ).exists()

    assert (
        OUTPUT /
        "kamailio-routing.cfg"
    ).exists()


if __name__ == "__main__":

    test_kamailio_adapter_runs()
    test_kamailio_output_exists()

    print("Kamailio adapter tests passed")
