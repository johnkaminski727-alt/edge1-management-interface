#!/usr/bin/env python3
"""Scoped Spamhaus rollback primitive. No action without explicit --execute.

This does not schedule a rollback or activate filtering. Keep an independently
installed root-owned copy for eventual recovery; do not rely on a mutable Git tree.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Callable, Sequence

FAMILY = "inet"
TABLE = "bigbird_spamhaus"
NFT = "/usr/sbin/nft"
Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def run_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), capture_output=True, text=True, check=False, timeout=20)


def present_tables(runner: Runner = run_command) -> set[tuple[str, str]]:
    result = runner([NFT, "-j", "list", "tables"])
    if result.returncode:
        raise RuntimeError("Unable to inspect nftables tables; refusing to assume absence")
    try:
        document = json.loads(result.stdout)
        records = document["nftables"]
        if not isinstance(records, list):
            raise ValueError
        tables = set()
        for entry in records:
            if not isinstance(entry, dict):
                raise ValueError
            table = entry.get("table")
            if table is None:
                continue
            if not isinstance(table, dict) or not isinstance(table.get("family"), str) or not isinstance(table.get("name"), str):
                raise ValueError
            tables.add((table["family"], table["name"]))
        return tables
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("Unable to parse nftables table listing; refusing deletion") from exc


def recover(runner: Runner = run_command, *, execute: bool = False) -> str:
    tables = present_tables(runner)
    target = (FAMILY, TABLE)
    if target not in tables:
        return "already_absent"
    if not execute:
        return "present_check_only"
    result = runner([NFT, "delete", "table", FAMILY, TABLE])
    if result.returncode:
        raise RuntimeError("Dedicated Spamhaus table deletion failed")
    if target in present_tables(runner):
        raise RuntimeError("Dedicated Spamhaus table remained after deletion")
    return "removed_verified"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-only", action="store_true", help="Inspect only (default)")
    mode.add_argument("--execute", action="store_true", help="Remove exactly inet bigbird_spamhaus if present")
    args = parser.parse_args()
    try:
        state = recover(execute=args.execute)
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, "STOP: " + str(exc) + "\n")
    print("Spamhaus scoped recovery:", state)


if __name__ == "__main__":
    main()
