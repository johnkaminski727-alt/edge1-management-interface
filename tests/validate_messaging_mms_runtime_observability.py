#!/usr/bin/env python3
"""Validate read-only MMS runtime observability without reading message content."""

import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

import messaging_gateway_collector as collector
from messaging_diagnostics import build_diagnostics
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
        return FakeResponse('{"status":"ready","storage":"postgres"}')
    return FakeResponse('{"detail":"Not Found"}', status=404)


health = collector.endpoint_payload("/healthz", opener=fake_opener)
ready = collector.endpoint_payload("/readyz", opener=fake_opener)
assert health == {"status": "ok"}
assert ready == {"status": "ready", "storage": "postgres"}
assert collector.endpoint_payload("/v1/management/status", opener=fake_opener) is None

with tempfile.TemporaryDirectory() as temporary:
    quarantine = Path(temporary) / "private-mms-quarantine"
    quarantine.mkdir(mode=0o700)
    present, secure = collector.quarantine_root_status(quarantine)
    assert present is True
    assert secure is True
    quarantine.chmod(0o755)
    present, secure = collector.quarantine_root_status(quarantine)
    assert present is True
    assert secure is False

with tempfile.TemporaryDirectory() as temporary:
    scanner = Path(temporary) / "clamscan"
    scanner.write_text("synthetic executable placeholder\n", encoding="utf-8")
    scanner.chmod(0o755)

    def fake_runner(*args, **kwargs):
        assert args[0] == [str(scanner), "--version"]
        assert kwargs["timeout"] == 3
        return subprocess.CompletedProcess(args[0], 0, "ClamAV 1.4.3/27390/Test\n", "")

    available, version = collector.trusted_scanner_status(scanner, runner=fake_runner)
    assert available is True
    assert version.startswith("ClamAV 1.4.3")

snapshot = health_snapshot(
    service_active=True,
    listener_reachable=True,
    storage_backend="postgres",
    mms_quarantine_root_present=True,
    mms_quarantine_root_secure=True,
    trusted_scanner_available=True,
    trusted_scanner_version="ClamAV 1.4.3",
).to_dict()
assert snapshot["state"] == "healthy"
assert snapshot["mms_security_ready"] is True
assert snapshot["production_actions_enabled"] is False

diagnostics = build_diagnostics(snapshot)
codes = {item["code"] for item in diagnostics["observations"]}
assert "mms_quarantine_secure" in codes
assert "mms_scanner_available" in codes
assert "mms_security_ready" in codes
assert "release_quarantine" in diagnostics["disabled_actions"]
assert diagnostics["production_actions_enabled"] is False

print("Messaging MMS runtime observability validation passed")
print("No message content, quarantine release, carrier traffic, or mutation path introduced")
