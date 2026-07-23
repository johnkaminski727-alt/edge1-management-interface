#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("mining_operations", ROOT / "server/mining_operations_exporter.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def miner(path: Path, **overrides):
    value = {
        "id": "miner-1",
        "name": "Miner 1",
        "enabled": True,
        "telemetry_path": str(path),
        "expected_hashrate_hs": 100,
        "amber_hashrate_ratio": 0.85,
        "red_hashrate_ratio": 0.50,
        "telemetry_fresh_seconds": 180,
        "telemetry_stale_seconds": 600,
    }
    value.update(overrides)
    return value


def write(path: Path, **values):
    payload = {"generated_unix": 1000, "online": True, "pool_connected": True, "hashrate_hs": 100}
    payload.update(values)
    path.write_text(json.dumps(payload), encoding="utf-8")


with tempfile.TemporaryDirectory() as directory:
    telemetry = Path(directory) / "telemetry.json"
    write(telemetry)
    assert MODULE.evaluate_miner(miner(telemetry), 1050)["health"]["state"] == "green"

    write(telemetry, hashrate_hs=70)
    assert MODULE.evaluate_miner(miner(telemetry), 1050)["health"]["state"] == "amber"

    write(telemetry, hashrate_hs=40)
    assert MODULE.evaluate_miner(miner(telemetry), 1050)["health"]["state"] == "red"

    write(telemetry, pool_connected=False)
    assert MODULE.evaluate_miner(miner(telemetry), 1050)["health"]["code"] == "pool_disconnected"

    write(telemetry)
    assert MODULE.evaluate_miner(miner(telemetry), 1250)["health"]["code"] == "telemetry_delayed"
    assert MODULE.evaluate_miner(miner(telemetry), 1700)["health"]["code"] == "telemetry_stale"
    assert MODULE.evaluate_miner(miner(telemetry, enabled=False), 1050)["health"]["state"] == "grey"

    fleet = MODULE.build_document({"miners": [miner(telemetry), miner(telemetry, id="disabled", enabled=False)]}, now=1050)
    assert fleet["format"] == "wwcx-mining-operations-v1"
    assert fleet["summary"]["configured"] == 2
    assert fleet["summary"]["active"] == 1
    assert fleet["overall"]["state"] == "green"

print("mining operations validation passed")
