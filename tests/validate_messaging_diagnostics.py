#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from messaging_diagnostics import build_diagnostics
from messaging_gateway_collector import collect_gateway_health

snapshot = collect_gateway_health().to_dict()
diagnostics = build_diagnostics(snapshot)
codes = {item["code"] for item in diagnostics["observations"]}

assert diagnostics["production_actions_enabled"] is False
assert "listener_unreachable" in codes
assert "send_sms" in diagnostics["disabled_actions"]
assert "send_mms" in diagnostics["disabled_actions"]
assert "carrier_test" in diagnostics["disabled_actions"]
assert "simulate_sandbox" in diagnostics["allowed_actions"]

print("Messaging diagnostics validation passed")
print("Known listener degradation represented without remediation")
