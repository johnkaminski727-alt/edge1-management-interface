#!/usr/bin/env python3
"""Build the public WW.CX mining operations status document from a miner registry.

The registry contains non-secret miner metadata, health thresholds, and telemetry
file locations. Pool credentials and payout addresses must never be placed here.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY = Path("/etc/wwcx-mining/miners.json")
DEFAULT_OUTPUT = Path("/var/www/edge1-status/mining-operations.json")
STATE_ORDER = {"green": 0, "grey": 1, "amber": 2, "red": 3}


def load_json(path: Path) -> Any:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def state(level: str, code: str, summary: str, details: list[str]) -> dict[str, Any]:
    return {"state": level, "code": code, "summary": summary, "details": details}


def evaluate_miner(entry: dict[str, Any], now: int) -> dict[str, Any]:
    miner_id = str(entry.get("id", "")).strip()
    enabled = entry.get("enabled", True) is True
    expected = number(entry.get("expected_hashrate_hs"))
    amber_ratio = number(entry.get("amber_hashrate_ratio"), 0.85)
    red_ratio = number(entry.get("red_hashrate_ratio"), 0.50)
    fresh_seconds = int(number(entry.get("telemetry_fresh_seconds"), 180))
    stale_seconds = int(number(entry.get("telemetry_stale_seconds"), 600))
    telemetry_path = Path(str(entry.get("telemetry_path", "")))
    telemetry = load_json(telemetry_path) if telemetry_path.as_posix() not in ("", ".") else {}
    telemetry = telemetry if isinstance(telemetry, dict) else {}

    generated = telemetry.get("generated_unix")
    age = max(0, now - generated) if isinstance(generated, int) else None
    online = telemetry.get("online") is True
    pool_connected = telemetry.get("pool_connected") is True
    hashrate = number(telemetry.get("hashrate_hs"))
    ratio = hashrate / expected if expected > 0 else None
    details: list[str] = []

    if not enabled:
        health = state("grey", "disabled", "Miner is intentionally disabled", ["Excluded from active fleet health."])
    elif not telemetry:
        health = state("grey", "telemetry_missing", "No telemetry has been received", [str(telemetry_path)])
    elif age is None:
        health = state("red", "telemetry_timestamp_missing", "Telemetry has no valid timestamp", [])
    elif age >= stale_seconds:
        health = state("red", "telemetry_stale", "Telemetry is stale", [f"Last update was {age} seconds ago."])
    elif not online:
        health = state("red", "miner_offline", "Miner reports offline", [f"Telemetry age: {age} seconds."])
    elif not pool_connected:
        health = state("red", "pool_disconnected", "Miner is not connected to its pool", [f"Telemetry age: {age} seconds."])
    elif age >= fresh_seconds:
        health = state("amber", "telemetry_delayed", "Telemetry is delayed", [f"Last update was {age} seconds ago."])
    elif expected <= 0:
        health = state("grey", "hashrate_expectation_missing", "No hashrate expectation is configured", [])
    elif ratio is not None and ratio < red_ratio:
        health = state("red", "hashrate_critical", "Hashrate is critically below expectation", [f"Operating at {ratio:.1%} of expected hashrate."])
    elif ratio is not None and ratio < amber_ratio:
        health = state("amber", "hashrate_degraded", "Hashrate is below expectation", [f"Operating at {ratio:.1%} of expected hashrate."])
    else:
        health = state("green", "healthy", "Miner is healthy", [f"Telemetry age: {age} seconds."])

    return {
        "id": miner_id,
        "name": str(entry.get("name", miner_id or "Unnamed miner")),
        "site": str(entry.get("site", "Unassigned")),
        "model": str(entry.get("model", "Unknown")),
        "algorithm": str(entry.get("algorithm", "sha256d")),
        "enabled": enabled,
        "health": health,
        "telemetry": {
            "age_seconds": age,
            "generated_unix": generated,
            "online": online,
            "hashrate_hs": round(hashrate, 3),
            "expected_hashrate_hs": round(expected, 3),
            "hashrate_ratio": round(ratio, 4) if ratio is not None else None,
            "temperature_c": round(number(telemetry.get("temperature_c")), 1),
            "fan_rpm": int(number(telemetry.get("fan_rpm"))),
            "power_watts": round(number(telemetry.get("power_watts")), 1),
            "accepted_shares": int(number(telemetry.get("accepted_shares"))),
            "rejected_shares": int(number(telemetry.get("rejected_shares"))),
        },
        "pool": {
            "name": str(entry.get("pool_name", "Not disclosed")),
            "connected": pool_connected,
            "worker": str(entry.get("worker_label", miner_id)),
        },
        "operations": {
            "location": str(entry.get("location", entry.get("site", "Unassigned"))),
            "owner": str(entry.get("owner", "WW.CX Operations")),
            "notes": str(entry.get("notes", "")),
        },
    }


def build_document(registry: dict[str, Any], now: int | None = None) -> dict[str, Any]:
    now = int(time.time()) if now is None else now
    raw_miners = registry.get("miners", [])
    miners = [evaluate_miner(item, now) for item in raw_miners if isinstance(item, dict)] if isinstance(raw_miners, list) else []
    active = [miner for miner in miners if miner["enabled"]]
    if not miners or not active:
        overall = state("grey", "no_active_miners", "No active miners are configured", [])
    else:
        worst = max((miner["health"]["state"] for miner in active), key=lambda value: STATE_ORDER[value])
        counts = {name: sum(1 for miner in active if miner["health"]["state"] == name) for name in STATE_ORDER}
        overall = state(worst, f"fleet_{worst}", f"Mining operations are {worst}", [f"{counts['green']} green, {counts['amber']} amber, {counts['red']} red, {counts['grey']} grey."])

    return {
        "format": "wwcx-mining-operations-v1",
        "generated_at": datetime.fromtimestamp(now, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "generated_unix": now,
        "overall": overall,
        "summary": {
            "configured": len(miners),
            "active": len(active),
            "green": sum(1 for miner in miners if miner["health"]["state"] == "green"),
            "amber": sum(1 for miner in miners if miner["health"]["state"] == "amber"),
            "red": sum(1 for miner in miners if miner["health"]["state"] == "red"),
            "grey": sum(1 for miner in miners if miner["health"]["state"] == "grey"),
            "total_hashrate_hs": round(sum(miner["telemetry"]["hashrate_hs"] for miner in active), 3),
            "expected_hashrate_hs": round(sum(miner["telemetry"]["expected_hashrate_hs"] for miner in active), 3),
        },
        "miners": miners,
        "health_rules": {
            "green": "Fresh telemetry, miner online, pool connected, and hashrate at or above the amber threshold.",
            "amber": "Telemetry is delayed but not stale, or hashrate is below the expected amber threshold.",
            "red": "Stale/invalid telemetry, offline miner, disconnected pool, or hashrate below the critical threshold.",
            "grey": "Disabled, missing telemetry, no active miners, or insufficient configuration to judge health.",
        },
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
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    registry = load_json(args.registry)
    atomic_write(args.output, build_document(registry if isinstance(registry, dict) else {}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
