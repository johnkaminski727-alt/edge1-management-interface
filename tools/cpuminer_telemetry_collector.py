#!/usr/bin/env python3
"""Collect sanitized cpuminer systemd telemetry for the WW.CX dashboard."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

HASHRATE_RE = re.compile(r"TTF @\s+([0-9]+(?:\.[0-9]+)?)\s*([kmgtpe]?h)/s", re.I)
BLOCK_RE = re.compile(r"(?:New (?:Stratum Diff [^,]+, )?(?:Work: )?Block|New Block)\s+(\d+)", re.I)
DIFF_RE = re.compile(r"Stratum(?: Diff)?\s+([0-9]+(?:\.[0-9]+)?)", re.I)
ACCEPTED_RE = re.compile(r"Accepted\s+(\d+)", re.I)
SUBMITTED_RE = re.compile(r"Submitted\s+(\d+)", re.I)
REJECTED_RE = re.compile(r"Rejected\s+(\d+)", re.I)

UNITS = {
    "h": 1.0,
    "kh": 1_000.0,
    "mh": 1_000_000.0,
    "gh": 1_000_000_000.0,
    "th": 1_000_000_000_000.0,
    "ph": 1_000_000_000_000_000.0,
    "eh": 1_000_000_000_000_000_000.0,
}


def run(*args: str) -> str:
    result = subprocess.run(args, check=False, text=True, capture_output=True)
    return result.stdout


def unit_property(unit: str, name: str) -> str:
    return run("systemctl", "show", unit, f"--property={name}", "--value").strip()


def parse_logs(text: str) -> dict[str, Any]:
    hashrate_hs = 0.0
    block_height = 0
    stratum_difficulty = 0.0
    accepted = 0
    submitted = 0
    rejected = 0

    for line in text.splitlines():
        match = HASHRATE_RE.search(line)
        if match:
            hashrate_hs = float(match.group(1)) * UNITS[match.group(2).lower()]
        match = BLOCK_RE.search(line)
        if match:
            block_height = int(match.group(1))
        match = DIFF_RE.search(line)
        if match and "Diff:" not in line:
            stratum_difficulty = float(match.group(1))
        match = SUBMITTED_RE.search(line)
        if match:
            submitted = int(match.group(1))
        match = ACCEPTED_RE.search(line)
        if match:
            accepted = int(match.group(1))
        match = REJECTED_RE.search(line)
        if match:
            rejected = int(match.group(1))

    return {
        "hashrate_hs": hashrate_hs,
        "network_block": block_height,
        "stratum_difficulty": stratum_difficulty,
        "submitted_shares": submitted,
        "accepted_shares": accepted,
        "rejected_shares": rejected,
    }


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit", default="wwcx-cpu-miner.service")
    parser.add_argument("--output", type=Path, default=Path("/var/lib/wwcx-mining/telemetry.json"))
    parser.add_argument("--pool", default="stratum.ckpool.org:3333")
    parser.add_argument("--worker", default="edge1")
    parser.add_argument("--journal-lines", type=int, default=500)
    args = parser.parse_args()

    logs = run("journalctl", "--unit", args.unit, "--no-pager", "--output=cat", "--lines", str(args.journal_lines))
    parsed = parse_logs(logs)
    active = unit_property(args.unit, "ActiveState") == "active"
    connected = active and "Stratum connection established" in logs and "Stratum connection failed" not in logs.splitlines()[-20:]

    payload = {
        "generated_unix": int(time.time()),
        "online": active,
        "pool_connected": connected,
        "benchmark": False,
        "miner_type": "cpuminer-opt",
        "algorithm": "sha256d",
        "pool": args.pool,
        "worker": args.worker,
        "hashrate_hs": parsed["hashrate_hs"],
        "hashrate_ths": parsed["hashrate_hs"] / 1_000_000_000_000.0,
        "network_block": parsed["network_block"],
        "stratum_difficulty": parsed["stratum_difficulty"],
        "submitted_shares": parsed["submitted_shares"],
        "accepted_shares": parsed["accepted_shares"],
        "rejected_shares": parsed["rejected_shares"],
        "unpaid_btc": "0.00000000",
    }
    atomic_write(args.output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
