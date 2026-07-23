#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from messaging_sandbox import simulate_message

valid = simulate_message({
    "sender_label": "Spirit Creek Telegraph Office",
    "recipient": "+15555550100",
    "body": "Synthetic sandbox test. No live delivery.",
})

assert valid["accepted"] is True
assert valid["status"] == "simulated_only"
assert valid["external_delivery_attempted"] is False
assert valid["production_actions_enabled"] is False
assert valid["stages"][-1] == "delivery_suppressed"

invalid = simulate_message({"recipient": "555-0100", "body": "test"})
assert invalid["accepted"] is False
assert invalid["external_delivery_attempted"] is False

print("Messaging sandbox validation passed")
print("External delivery suppression confirmed")
