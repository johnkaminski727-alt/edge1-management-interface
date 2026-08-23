#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from messaging_diagnostics import build_diagnostics
from messaging_gateway_collector import collect_gateway_health
from messaging_health_models import health_snapshot

healthy = build_diagnostics(
    health_snapshot(service_active=True, listener_reachable=True).to_dict()
)
healthy_codes = {item["code"] for item in healthy["observations"]}
assert "listener_reachable" in healthy_codes
assert "listener_unreachable" not in healthy_codes

degraded = build_diagnostics(
    health_snapshot(service_active=True, listener_reachable=False).to_dict()
)
degraded_codes = {item["code"] for item in degraded["observations"]}
assert "listener_unreachable" in degraded_codes
assert "listener_reachable" not in degraded_codes

snapshot = collect_gateway_health().to_dict()
live = build_diagnostics(snapshot)
live_codes = {item["code"] for item in live["observations"]}
expected_listener_code = (
    "listener_reachable" if snapshot["listener_reachable"] else "listener_unreachable"
)

assert expected_listener_code in live_codes
assert live["production_actions_enabled"] is False
assert "send_sms" in live["disabled_actions"]
assert "send_mms" in live["disabled_actions"]
assert "carrier_test" in live["disabled_actions"]
assert "simulate_sandbox" in live["allowed_actions"]

print("Messaging diagnostics validation passed")
print("Healthy and degraded listener states represented without remediation")
