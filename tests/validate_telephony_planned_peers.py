#!/usr/bin/env python3
"""Validate planned SIP peer semantics without probing or changing a carrier."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

import telephony_status_server as telephony

registry = {
    "carriers": [
        {"id": "configured-carrier", "name": "Configured", "status": "testing"},
        {"id": "planned-carrier", "name": "Planned", "status": "planned"},
    ],
    "sip_peers": [
        {
            "id": "configured-peer",
            "carrier_id": "configured-carrier",
            "endpoint": "127.0.0.1",
            "transport": "udp",
        },
        {
            "id": "planned-peer",
            "carrier_id": "planned-carrier",
            "endpoint": "pending",
            "transport": "tls",
        },
    ],
    "routing_rules": [],
}
health = {
    "peers": {
        "configured-peer": {
            "status": "healthy",
            "sip_options": {"response_code": 200, "latency_ms": 1.25},
        },
        "planned-peer": {
            "status": "failed",
            "sip_options": {"error": "Name or service not known"},
        },
    }
}

original_loader = telephony.load_json_file
try:
    def fake_loader(path):
        if path == telephony.INTERCONNECT_REGISTRY:
            return registry
        if path == telephony.PEER_STATUS:
            return health
        return {}

    telephony.load_json_file = fake_loader
    rows = telephony.sip_interconnect_snapshot()
    by_name = {row["name"]: row for row in rows}

    configured = by_name["configured-peer"]
    assert configured["health_check_applicable"] is True
    assert configured["status"] == "healthy"
    assert configured["success_rate"] == 100
    assert configured["latency_ms"] == 1.25

    planned = by_name["planned-peer"]
    assert planned["health_check_applicable"] is False
    assert planned["lifecycle"] == "planned"
    assert planned["status"] == "planned"
    assert planned["success_rate"] is None
    assert planned["latency_ms"] is None

    acceptance = telephony.acceptance_payload()
    acceptance_by_peer = {row["peer"]: row for row in acceptance["sip_peer_tests"]}
    assert acceptance_by_peer["configured-peer"]["status"] == "healthy"
    assert acceptance_by_peer["planned-peer"]["status"] == "planned"
    assert acceptance_by_peer["planned-peer"]["health_check_applicable"] is False

    lifecycle = telephony.carrier_lifecycle_payload()
    by_carrier = {carrier["id"]: carrier for carrier in lifecycle["carriers"]}
    assert by_carrier["configured-carrier"]["sip_peers"] == [
        {"peer": "configured-peer", "status": "healthy", "health_check_applicable": True}
    ]
    assert by_carrier["planned-carrier"]["sip_peers"] == [
        {"peer": "planned-peer", "status": "planned", "health_check_applicable": False}
    ]
finally:
    telephony.load_json_file = original_loader

source = (ROOT / "server" / "telephony_status_server.py").read_text(encoding="utf-8")
assert '"trunks_planned"' in source
assert '"health_check_applicable"' in source
assert 'endpoint.strip().lower() != "pending"' in source
assert "channel originate" not in source

print("Telephony planned-peer semantics validation passed")
print("Planned/pending peers no longer count as failed operational trunks")
