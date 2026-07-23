#!/usr/bin/env python3
"""Publish a compact sanitized 24-hour Bitcoin mining history summary."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_history(path: Path, cutoff: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.is_file():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        generated = item.get("generated_unix")
        samples = item.get("hashrate_samples")
        if (
            isinstance(item, dict)
            and isinstance(generated, int)
            and generated >= cutoff
            and isinstance(samples, int)
            and samples >= 3
        ):
            records.append(item)
    return sorted(records, key=lambda item: item["generated_unix"])


def build_summary(records: list[dict[str, Any]], now: int) -> dict[str, Any]:
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in records:
        bucket = int(item["generated_unix"]) // 3600 * 3600
        buckets[bucket].append(item)

    points: list[dict[str, Any]] = []
    for bucket in sorted(buckets):
        samples = buckets[bucket]
        rates = [float(item.get("hashrate_hs", 0.0)) for item in samples]
        online = sum(item.get("online") is True for item in samples)
        connected = sum(item.get("pool_connected") is True for item in samples)
        count = len(samples)
        points.append({
            "hour_unix": bucket,
            "hour": datetime.fromtimestamp(bucket, timezone.utc).strftime("%Y-%m-%dT%H:00:00Z"),
            "samples": count,
            "hashrate_avg_hs": round(sum(rates) / count, 3) if count else 0.0,
            "hashrate_min_hs": round(min(rates), 3) if rates else 0.0,
            "hashrate_max_hs": round(max(rates), 3) if rates else 0.0,
            "uptime_percent": round(online * 100.0 / count, 2) if count else 0.0,
            "pool_connected_percent": round(connected * 100.0 / count, 2) if count else 0.0,
        })

    rates = [float(item.get("hashrate_hs", 0.0)) for item in records]
    count = len(records)
    latest = records[-1] if records else {}
    return {
        "format": "wwcx-bitcoin-mining-history-v1",
        "generated_at": datetime.fromtimestamp(now, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "generated_unix": now,
        "window_seconds": 86400,
        "sample_count": count,
        "summary": {
            "hashrate_avg_hs": round(sum(rates) / count, 3) if count else 0.0,
            "hashrate_min_hs": round(min(rates), 3) if rates else 0.0,
            "hashrate_max_hs": round(max(rates), 3) if rates else 0.0,
            "uptime_percent": round(sum(item.get("online") is True for item in records) * 100.0 / count, 2) if count else 0.0,
            "pool_connected_percent": round(sum(item.get("pool_connected") is True for item in records) * 100.0 / count, 2) if count else 0.0,
            "accepted_shares": int(latest.get("accepted_shares", 0)),
            "rejected_shares": int(latest.get("rejected_shares", 0)),
        },
        "hourly": points[-24:],
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
    parser.add_argument("--history", type=Path, default=Path("/var/lib/wwcx-mining/telemetry-history.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("/var/www/edge1-status/bitcoin-mining-history.json"))
    parser.add_argument("--window-seconds", type=int, default=86400)
    args = parser.parse_args()
    now = int(time.time())
    atomic_write(args.output, build_summary(load_history(args.history, now - args.window_seconds), now))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
