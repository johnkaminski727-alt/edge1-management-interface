#!/usr/bin/env python3
"""Read-only, bounded boot readiness gate for future Spamhaus restoration.

No firewall changes, timer installation, service start or DNS updates.
The existing Spamhaus table is recognized as already active, not replaced.
"""
from __future__ import annotations

import argparse
import subprocess
from collections.abc import Callable, Sequence

SERVICES = (
    "ufw.service",
    "crowdsec.service",
    "crowdsec-firewall-bouncer.service",
    "ssh.service",
)
NFT = "/usr/sbin/nft"
Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def run_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), capture_output=True, text=True,
                          check=False, timeout=12)


def inspect(runner: Runner = run_command) -> str:
    ntp = runner(["/usr/bin/timedatectl", "show", "-p", "NTPSynchronized", "--value"])
    if ntp.returncode != 0 or ntp.stdout.strip().lower() != "yes":
        raise RuntimeError("System clock is not confirmed NTP synchronized")

    chrony = runner(["/usr/bin/chronyc", "tracking"])
    if chrony.returncode != 0:
        raise RuntimeError("Chrony tracking unavailable")
    leaps = [
        line.partition(":")[2].strip()
        for line in chrony.stdout.splitlines()
        if line.split(":", 1)[0].strip() == "Leap status"
    ]
    if leaps != ["Normal"]:
        raise RuntimeError("Chrony leap state is not confirmed Normal")

    for unit in SERVICES:
        service = runner(["/usr/bin/systemctl", "is-active", unit])
        if service.returncode != 0 or service.stdout.strip() != "active":
            raise RuntimeError("Required service is not active: " + unit)

    table = runner([NFT, "list", "table", "inet", "bigbird_spamhaus"])
    if table.returncode == 0:
        return "already_active"

    # ENOENT exit code is not distinguished from other nft errors by returncode.
    # Inspect the JSON full table inventory so query errors never look like absence.
    inventory = runner([NFT, "-j", "list", "tables"])
    if inventory.returncode != 0:
        raise RuntimeError("Cannot verify whether Spamhaus table is absent")
    import json
    try:
        records = json.loads(inventory.stdout)["nftables"]
        if not isinstance(records, list):
            raise ValueError("Invalid tables listing")
        tables = set()
        for item in records:
            if not isinstance(item, dict):
                raise ValueError("Invalid tables record")
            table_info = item.get("table")
            if table_info is None:
                continue
            if not isinstance(table_info, dict):
                raise ValueError("Invalid table record")
            family, name = table_info["family"], table_info["name"]
            if not isinstance(family, str) or not isinstance(name, str):
                raise ValueError("Invalid table identifier")
            tables.add((family, name))
    except (ValueError, TypeError, KeyError) as exc:
        raise RuntimeError("Cannot interpret nftables table inventory") from exc
    if ("inet", "bigbird_spamhaus") in tables:
        raise RuntimeError("Inconsistent Spamhaus table presence")
    return "eligible_for_separate_candidate_validation"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true",
                        help="Readiness inspection only (also the default)")
    args = parser.parse_args()
    try:
        result = inspect()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(1, "STOP: " + str(exc) + "\n")
    print("PASS: Spamhaus boot readiness:", result)
    print("CHECK ONLY: no nftables or systemd changes")


if __name__ == "__main__":
    main()
