#!/usr/bin/env python3
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools" / "bitcoin_mining_history_summary.py"
spec = importlib.util.spec_from_file_location("summary", MODULE)
summary = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(summary)

records = [
    {"generated_unix": 3600, "hashrate_hs": 280000.0, "online": True, "pool_connected": True, "accepted_shares": 0, "rejected_shares": 0},
    {"generated_unix": 3660, "hashrate_hs": 300000.0, "online": True, "pool_connected": True, "accepted_shares": 0, "rejected_shares": 0},
    {"generated_unix": 7200, "hashrate_hs": 290000.0, "online": False, "pool_connected": False, "accepted_shares": 1, "rejected_shares": 0},
]
payload = summary.build_summary(records, 7300)
assert payload["format"] == "wwcx-bitcoin-mining-history-v1"
assert payload["sample_count"] == 3
assert payload["summary"]["hashrate_avg_hs"] == 290000.0
assert payload["summary"]["uptime_percent"] == 66.67
assert payload["summary"]["pool_connected_percent"] == 66.67
assert payload["summary"]["accepted_shares"] == 1
assert len(payload["hourly"]) == 2
assert payload["hourly"][0]["hashrate_avg_hs"] == 290000.0
print("Bitcoin mining history summary validation passed")
