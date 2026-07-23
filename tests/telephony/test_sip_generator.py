#!/usr/bin/env python3

from pathlib import Path
import subprocess


BASE = Path(__file__).resolve().parents[2]

GENERATOR = BASE / "tools/telephony/generate_sip_config.py"

OUTPUT = BASE / "generated/telephony"


def test_generator_runs():

    result = subprocess.run(
        ["python3", str(GENERATOR)],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0


def test_generated_files_exist():

    assert (
        OUTPUT / "peers.conf"
    ).exists()

    assert (
        OUTPUT / "routing.conf"
    ).exists()

    assert (
        OUTPUT / "security.conf"
    ).exists()


if __name__ == "__main__":

    test_generator_runs()
    test_generated_files_exist()

    print("SIP generator tests passed")
