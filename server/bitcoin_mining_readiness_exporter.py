#!/usr/bin/env python3
"""Export a sanitized Bitcoin mining-readiness document.

This module does not start mining, connect to a pool, configure a payout
address, or handle credentials. It reports only readiness and optional local
telemetry supplied by an operator-controlled JSON file.
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

DEFAULT_CONFIG = Path("/etc/wwcx-mining/readiness.json")
DEFAULT_TELEMETRY = Path("/var/lib/wwcx-mining/telemetry.json")
DEFAULT_OUTPUT = Path("/var/www/edge1-status/bitcoin-mining.json")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def safe_number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_document(config: dict[str, Any], telemetry: dict[str, Any]) -> dict[str, Any]:
    enabled = config.get("enabled") is True
    hardware = config.get("hardware") if isinstance(config.get("hardware"), dict) else {}
    economics = config.get("economics") if isinstance(config.get("economics"), dict) else {}

    hashrate_hs = safe_number(telemetry.get("hashrate_hs"))
    hashrate_ths = safe_number(telemetry.get("hashrate_ths"))

    if hashrate_hs <= 0 and hashrate_ths > 0:
        hashrate_hs = hashrate_ths * 1_000_000_000_000.0
    elif hashrate_ths <= 0 and hashrate_hs > 0:
        hashrate_ths = hashrate_hs / 1_000_000_000_000.0

    hashrate_khs = hashrate_hs / 1000.0
    if hashrate_hs >= 1_000_000:
        hashrate_display = f"{hashrate_hs / 1_000_000:.2f} MH/s"
    elif hashrate_hs >= 1000:
        hashrate_display = f"{hashrate_khs:.2f} kH/s"
    else:
        hashrate_display = f"{hashrate_hs:.2f} H/s"

    power_watts = safe_number(telemetry.get("power_watts", hardware.get("rated_power_watts", 0)))
    electricity_per_kwh = safe_number(economics.get("electricity_cost_per_kwh"))
    daily_energy_kwh = power_watts * 24.0 / 1000.0
    daily_power_cost = daily_energy_kwh * electricity_per_kwh

    configured = bool(hardware.get("model")) and power_watts > 0
    telemetry_age = None
    generated = telemetry.get("generated_unix")
    if isinstance(generated, int):
        telemetry_age = max(0, int(time.time()) - generated)

    online = enabled and telemetry.get("online") is True and telemetry_age is not None and telemetry_age < 180

    return {
        "format": "wwcx-bitcoin-mining-status-v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "generated_unix": int(time.time()),
        "mode": "readiness" if not enabled else "monitoring",
        "mining_enabled": enabled,
        "miner": {
            "configured": configured,
            "online": online,
            "model": str(hardware.get("model", "Not selected")),
            "hashrate_hs": round(hashrate_hs, 3),
            "hashrate_khs": round(hashrate_khs, 6),
            "hashrate_ths": hashrate_ths,
            "hashrate_display": hashrate_display,
            "benchmark": telemetry.get("benchmark") is True,
            "benchmark_seconds": round(safe_number(telemetry.get("benchmark_seconds")), 3),
            "benchmark_hashes": int(safe_number(telemetry.get("benchmark_hashes"))),
            "power_watts": round(power_watts, 1),
            "temperature_c": round(safe_number(telemetry.get("temperature_c")), 1),
            "fan_rpm": int(safe_number(telemetry.get("fan_rpm"))),
            "accepted_shares": int(safe_number(telemetry.get("accepted_shares"))),
            "rejected_shares": int(safe_number(telemetry.get("rejected_shares"))),
        },
        "economics": {
            "electricity_cost_per_kwh": round(electricity_per_kwh, 5),
            "estimated_daily_energy_kwh": round(daily_energy_kwh, 3),
            "estimated_daily_power_cost": round(daily_power_cost, 2),
            "currency": str(economics.get("currency", "CAD")),
        },
        "pool": {
            "configured": config.get("pool_configured") is True,
            "connected": telemetry.get("pool_connected") is True if enabled else False,
            "unpaid_btc": str(telemetry.get("unpaid_btc", "0.00000000")),
        },
        "payout": {
            "wallet_monitored": True,
            "destination_configured": config.get("payout_configured") is True,
            "address_exposed": False,
        },
        "warnings": [] if configured else ["hardware_not_configured"],
    }


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
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
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--telemetry", type=Path, default=DEFAULT_TELEMETRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    document = build_document(load_json(args.config), load_json(args.telemetry))
    atomic_write(args.output, document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
