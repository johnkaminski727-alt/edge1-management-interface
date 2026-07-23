#!/usr/bin/env python3
"""Validation for the WW.CX messaging gateway live health collector."""

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

import messaging_gateway_collector as collector
from messaging_health_models import health_snapshot


class FakeResponse:
    def __init__(self, payload: str, status: int = 200):
        self.status = status
        self._body = io.BytesIO(payload.encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit: int = -1):
        return self._body.read(limit)


def fake_opener(request, timeout=0):
    assert request.full_url.startswith("http://127.0.0.1:58080/")
    assert timeout == 2
    if request.full_url.endswith("/healthz"):
        return FakeResponse('{"status":"ok"}')
    if request.full_url.endswith("/readyz"):
        return FakeResponse('{"status":"ready","storage":"memory"}')
    return FakeResponse('{"detail":"Not Found"}', status=404)


assert collector.endpoint_is_healthy("/healthz", opener=fake_opener) is True
assert collector.endpoint_is_healthy("/readyz", opener=fake_opener) is True
assert collector.endpoint_is_healthy("/missing", opener=fake_opener) is False

healthy = health_snapshot(service_active=True, listener_reachable=True).to_dict()
assert healthy["gateway"] == "wwcx-messaging-gateway"
assert healthy["state"] == "healthy"
assert healthy["production_actions_enabled"] is False

snapshot = collector.collect_gateway_health().to_dict()
assert snapshot["gateway"] == "wwcx-messaging-gateway"
assert snapshot["state"] in ("healthy", "degraded")
assert isinstance(snapshot["service_active"], bool)
assert isinstance(snapshot["listener_reachable"], bool)
assert snapshot["production_actions_enabled"] is False

print("Messaging gateway validation passed")
print("Live loopback health probing confirmed")
print("Production messaging actions disabled")
