#!/usr/bin/env python3
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools" / "cpuminer_telemetry_collector.py"
spec = importlib.util.spec_from_file_location("collector", MODULE)
collector = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(collector)

sample = """
Stratum connection established
New Stratum Diff 10000, Block 959300, Tx 10, Job abc
TTF @ 294.77 kh/s: Block 1y, Share 4y
Submitted             3            3
Accepted              2            2        66.7%
Rejected              1            1
"""
parsed = collector.parse_logs(sample)
assert parsed["hashrate_hs"] == 294770.0, parsed
assert parsed["network_block"] == 959300, parsed
assert parsed["stratum_difficulty"] == 10000.0, parsed
assert parsed["submitted_shares"] == 3, parsed
assert parsed["accepted_shares"] == 2, parsed
assert parsed["rejected_shares"] == 1, parsed
print("cpuminer telemetry validation passed")
