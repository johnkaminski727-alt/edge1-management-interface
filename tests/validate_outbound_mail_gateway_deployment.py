#!/usr/bin/env python3
"""Validate the disabled Phase A deployment assets for the outbound-mail gateway."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/messaging/outbound-mail-gateway.json"
POLICY = ROOT / "config/messaging/outbound-mail-policy.json"
IDENTITIES = ROOT / "config/messaging/mail-identities.json"
SERVER = ROOT / "server/outbound_mail_gateway_server.py"
UNIT = ROOT / "deploy/messaging/wwcx-outbound-mail-gateway.service"
INSTALLER = ROOT / "deploy/messaging/install-outbound-mail-gateway.sh"
SMOKE = ROOT / "deploy/messaging/outbound-mail-gateway-smoke-test.sh"
ELECTRUM_UNIT = ROOT / "deploy/systemd/edge1-electrum-watch-api.service"
RUNBOOK = ROOT / "docs/messaging-operations/outbound-mail-phase-a-deployment-20260801.md"
PORT = 8104


config = json.loads(CONFIG.read_text(encoding="utf-8"))
policy = json.loads(POLICY.read_text(encoding="utf-8"))
identities = json.loads(IDENTITIES.read_text(encoding="utf-8"))
unit = UNIT.read_text(encoding="utf-8")
installer = INSTALLER.read_text(encoding="utf-8")
smoke = SMOKE.read_text(encoding="utf-8")
electrum_unit = ELECTRUM_UNIT.read_text(encoding="utf-8")
runbook = RUNBOOK.read_text(encoding="utf-8")

assert config["listen"] == {"host": "127.0.0.1", "port": PORT}
assert config["enabled"] is False
assert config["deployment_authorized"] is False
assert config["external_delivery_authorized"] is False
assert config["admin"]["send_endpoint_enabled"] is False
assert config["preparation_api"]["enabled"] is False
assert config["provider"]["selected"] == "none"
assert not any(profile["enabled"] for profile in config["provider"]["profiles"].values())
assert policy["enabled"] is False
assert policy["smtp_cutover_authorized"] is False
assert policy["delivery"]["allow_external_submission"] is False
assert policy["delivery"]["allow_live_delivery"] is False
assert identities["outbound_activation_authorized"] is False
assert not any(profile["outbound_enabled"] for profile in identities["sender_profiles"].values())

assert "--port 8094" in electrum_unit, "Electrum service reservation changed unexpectedly"
assert f"--port {PORT}" in unit
assert "127.0.0.1" in unit
assert "User=wwcx-mail-gateway" in unit
assert "ProtectSystem=strict" in unit
assert "NoNewPrivileges=true" in unit
assert "ReadWritePaths=/opt/edge1-management-interface/var/outbound-mail" in unit
assert "EnvironmentFile=" not in unit
assert "WWCX_MAIL_GATEWAY_TOKEN=" not in unit

for required in (
    'branch" != "main"',
    "diff --quiet",
    "EXPECTED_COMMIT",
    "Port $PORT is already occupied",
    'config["deployment_authorized"] is False',
    'config["external_delivery_authorized"] is False',
    'config["preparation_api"]["enabled"] is False',
    'identities["outbound_activation_authorized"] is False',
    'profile["outbound_enabled"]',
    "groupadd --system",
    "useradd --system --gid",
    "systemctl daemon-reload",
    "systemctl enable",
    "systemctl restart",
    "rollback()",
    "service-after-rollback.txt",
    "source-sha256.txt",
    "SHA256SUMS",
    "outbound-mail-gateway-smoke-test.sh",
):
    assert required in installer, required

for required in (
    'status["state"] == "disabled"',
    'status["external_delivery_enabled"] is False',
    'status["preparation_api"]["enabled"] is False',
    'payload["error"] == "preparation_api_disabled"',
    'payload["error"] == "delivery_disabled"',
    "Unsafe non-loopback listener",
):
    assert required in smoke, required

for required in (
    "Port 8094 conflict",
    "8104",
    "EXPECTED_COMMIT",
    "rollback",
    "no external preparation",
    "no external delivery",
):
    assert required.casefold() in runbook.casefold(), required

for path in (INSTALLER, SMOKE):
    result = subprocess.run(["sh", "-n", str(path)], cwd=ROOT, check=False)
    assert result.returncode == 0, path

if shutil.which("ss") is None:
    raise AssertionError("ss is required by the Phase A smoke test")

with tempfile.TemporaryDirectory(prefix="wwcx-outbound-mail-deploy-") as temporary:
    temporary_path = pathlib.Path(temporary)
    stdout_path = temporary_path / "server.stdout"
    stderr_path = temporary_path / "server.stderr"
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        process = subprocess.Popen(
            [
                sys.executable,
                str(SERVER),
                "--config",
                str(CONFIG),
                "--identities",
                str(IDENTITIES),
                "--host",
                "127.0.0.1",
                "--port",
                str(PORT),
            ],
            cwd=ROOT,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
        )
        try:
            deadline = time.monotonic() + 10
            while True:
                if process.poll() is not None:
                    raise AssertionError(
                        "gateway server exited during deployment validation: "
                        + stderr_path.read_text(encoding="utf-8")
                    )
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{PORT}/outbound-mail/healthz", timeout=1
                    ) as response:
                        if response.status == 200:
                            break
                except (urllib.error.URLError, TimeoutError):
                    pass
                if time.monotonic() >= deadline:
                    raise AssertionError("gateway server did not become healthy")
                time.sleep(0.2)

            environment = os.environ.copy()
            environment.update({"HOST": "127.0.0.1", "PORT": str(PORT)})
            result = subprocess.run(
                ["sh", str(SMOKE)],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            assert "External delivery: rejected" in result.stdout
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

print("Outbound mail Phase A deployment validation passed")
print("Electrum remains on 8094; disabled outbound mail gateway uses loopback 8104")
print("Installer preflight, rollback, evidence capture, and no-send smoke test verified")
