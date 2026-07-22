#!/usr/bin/env python3
"""
Validation for WW.CX messaging operations visibility foundation.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"

sys.path.insert(0, str(SERVER))

from messaging_gateway_collector import collect_gateway_health


snapshot = collect_gateway_health().to_dict()

assert snapshot["gateway"] == "wwcx-messaging-gateway"
assert snapshot["state"] == "degraded"
assert snapshot["production_actions_enabled"] is False
assert "service_active" in snapshot
assert "listener_reachable" in snapshot

print("Messaging gateway validation passed")
print("Read-only telemetry boundary preserved")
print("Production messaging actions disabled")
