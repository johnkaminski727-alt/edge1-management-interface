#!/usr/bin/env python3
from pathlib import Path
import importlib.util
import json
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools" / "cpuminer_telemetry_collector.py"
spec = importlib.util.spec_from_file_location("collector", MODULE)
collector = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(collector)

with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / "history.jsonl"
    collector.append_history(path, {"generated_unix": 100, "hashrate_hs": 1.0}, 10**12)
    collector.append_history(path, {"generated_unix": 200, "hashrate_hs": 2.0}, 10**12)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows == [
        {"generated_unix": 100, "hashrate_hs": 1.0},
        {"generated_unix": 200, "hashrate_hs": 2.0},
    ], rows

print("cpuminer history validation passed")
