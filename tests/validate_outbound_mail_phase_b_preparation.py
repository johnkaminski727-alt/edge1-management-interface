#!/usr/bin/env python3
"""Validate the staged Phase B preparation-only activation package."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/messaging/outbound-mail-gateway.json"
SERVER = ROOT / "server/outbound_mail_gateway_server.py"
DROPIN = ROOT / "deploy/messaging/wwcx-outbound-mail-preparation-api.conf"
INSTALLER = ROOT / "deploy/messaging/install-outbound-mail-preparation-api.sh"
CANARY = ROOT / "tools/outbound_mail_preparation_canary.py"
PROXY = ROOT / "deploy/messaging/outbound-mail-preparation-api-nginx.conf.example"
RUNBOOK = ROOT / "docs/messaging-operations/outbound-mail-phase-b-preparation-20260801.md"
PORT = 8104
SECRET = "phaseB_test_secret_ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789"

for path in (DROPIN, INSTALLER, CANARY, PROXY, RUNBOOK):
    assert path.is_file(), path

config = json.loads(CONFIG.read_text(encoding="utf-8"))
assert config["preparation_api"]["enabled"] is False
assert config["enabled"] is False
assert config["external_delivery_authorized"] is False
assert config["admin"]["send_endpoint_enabled"] is False
assert config["provider"]["selected"] == "none"
assert not any(profile["enabled"] for profile in config["provider"]["profiles"].values())

dropin = DROPIN.read_text(encoding="utf-8")
assert "EnvironmentFile=/etc/wwcx/outbound-mail-gateway.env" in dropin
assert "--config /etc/wwcx/outbound-mail-gateway.json" in dropin
assert "--host 127.0.0.1 --port 8104" in dropin
assert "Environment=WWCX_MAIL_GATEWAY_TOKEN=" not in dropin

installer = INSTALLER.read_text(encoding="utf-8")
for required in (
    "SECRET_SOURCE_FILE is required",
    "must be owned by root",
    "mode must be 0400 or 0600",
    'config["preparation_api"]["enabled"] = True',
    "systemctl restart",
    "outbound_mail_preparation_canary.py",
    "Phase B1 operation failed; restoring",
    "ACTION must be install or disable",
    "TLS reverse proxy: not installed",
    "External delivery: disabled",
    "rollback_dir=$(mktemp -d)",
    "rm -rf \"$rollback_dir\"",
):
    assert required in installer, required
for prohibited in (
    "openssl rand",
    "secrets.token_urlsafe",
    "uuidgen",
    "WWCX_MAIL_GATEWAY_TOKEN=changeme",
    'backup_dir="$EVIDENCE_DIR/rollback"',
):
    assert prohibited not in installer, prohibited

proxy = PROXY.read_text(encoding="utf-8")
assert proxy.count("proxy_pass http://127.0.0.1:8104;") == 2
assert "location = /outbound-mail/api/v1/status" in proxy
assert "location = /outbound-mail/api/v1/prepare" in proxy
assert "limit_except GET" in proxy
assert "limit_except POST" in proxy
assert "allow PREPARATION_CLIENT_CIDR;" in proxy
assert "location /" in proxy and "return 404;" in proxy
assert "proxy_redirect off;" in proxy
assert "X-Forwarded-For \"\"" in proxy
assert "location /outbound-mail/" not in proxy

runbook = RUNBOOK.read_text(encoding="utf-8")
for required in (
    "B1 — loopback authenticated preparation",
    "B2 — TLS reverse proxy",
    "never copies the secret",
    "prepared_not_sent",
    "409 replay_detected",
    "403 delivery_disabled",
    "ACTION=disable",
    "must not be installed as-is",
):
    assert required in runbook, required

result = subprocess.run(["sh", "-n", str(INSTALLER)], cwd=ROOT, check=False)
assert result.returncode == 0, INSTALLER

with tempfile.TemporaryDirectory(prefix="wwcx-phase-b-") as temporary:
    temp = pathlib.Path(temporary)
    secret_file = temp / "secret"
    secret_file.write_text(SECRET + "\n", encoding="utf-8")
    secret_file.chmod(0o600)

    runtime_config = json.loads(json.dumps(config))
    runtime_config["preparation_api"]["enabled"] = True
    audit_name = f"phase-b-audit-{os.getpid()}.jsonl"
    nonce_name = f"phase-b-nonces-{os.getpid()}.sqlite3"
    runtime_config["paths"]["audit_jsonl"] = f"var/outbound-mail/{audit_name}"
    runtime_config["preparation_api"]["nonce_store"] = f"var/outbound-mail/{nonce_name}"
    runtime_path = temp / "runtime.json"
    runtime_path.write_text(json.dumps(runtime_config), encoding="utf-8")
    audit_path = ROOT / "var/outbound-mail" / audit_name
    nonce_path = ROOT / "var/outbound-mail" / nonce_name

    env = os.environ.copy()
    env["WWCX_MAIL_GATEWAY_TOKEN"] = SECRET
    process = subprocess.Popen(
        [
            sys.executable,
            str(SERVER),
            "--config",
            str(runtime_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while True:
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                raise AssertionError(f"gateway exited early\n{stdout}\n{stderr}")
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{PORT}/outbound-mail/healthz", timeout=1
                ) as response:
                    if response.status == 200:
                        break
            except (urllib.error.URLError, TimeoutError):
                pass
            if time.monotonic() >= deadline:
                raise AssertionError("gateway did not become ready")
            time.sleep(0.2)

        result = subprocess.run(
            [
                sys.executable,
                str(CANARY),
                "--secret-file",
                str(secret_file),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Signed preparation: prepared_not_sent" in result.stdout
        assert "Nonce replay: rejected" in result.stdout
        assert "External delivery: rejected" in result.stdout

        audit_text = audit_path.read_text(encoding="utf-8")
        assert "outbound_message_prepared_api" in audit_text
        assert "prepared_not_sent" in audit_text
        assert SECRET not in audit_text
        assert "This synthetic canary must be prepared but never sent." not in audit_text
        assert "action_token" not in audit_text
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        for path in (audit_path, nonce_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

print("Outbound mail Phase B preparation package validation passed")
print("Runtime overlay, HMAC canary, replay rejection, audit redaction, and no-send state verified")
print("TLS proxy remains a staged exact-route template with placeholders")
