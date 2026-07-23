#!/usr/bin/env python3
"""Run a bounded, non-networked SHA-256 throughput experiment.

This is not a Bitcoin miner. It performs double-SHA-256 locally with one
process, writes sanitized telemetry, and never reads wallet data or contacts a
pool.
"""
import argparse
import hashlib
import json
import os
import platform
import tempfile
import time
from pathlib import Path


def atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, 0o644)
        os.replace(name, str(path))
    finally:
        try:
            os.unlink(name)
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--output", type=Path, default=Path("/var/lib/wwcx-mining/telemetry.json"))
    args = parser.parse_args()
    if args.seconds < 10 or args.seconds > 300:
        raise SystemExit("seconds must be between 10 and 300")

    started = time.time()
    deadline = started + args.seconds
    count = 0
    seed = bytearray(os.urandom(80))
    digest = b""
    while time.time() < deadline:
        nonce = count.to_bytes(8, "little", signed=False)
        digest = hashlib.sha256(hashlib.sha256(bytes(seed) + nonce).digest()).digest()
        count += 1

    elapsed = max(time.time() - started, 0.001)
    hashes_per_second = count / elapsed
    payload = {
        "generated_unix": int(time.time()),
        "online": False,
        "pool_connected": False,
        "benchmark": True,
        "benchmark_seconds": round(elapsed, 3),
        "benchmark_hashes": count,
        "hashrate_hs": round(hashes_per_second, 3),
        "hashrate_ths": round(hashes_per_second / 1000000000000.0, 12),
        "cpu_count": os.cpu_count() or 1,
        "platform": platform.machine(),
        "accepted_shares": 0,
        "rejected_shares": 0,
        "unpaid_btc": "0.00000000",
        "proof_prefix": digest.hex()[:12],
    }
    atomic_write(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
