#!/usr/bin/env python3
"""Repository validation for the disabled WW.CX inbound mail hub."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
CONFIG_PATH = ROOT / "config" / "messaging" / "inbound-mail-hub.json"
CORE_PATH = SERVER_ROOT / "inbound_mail_hub.py"
SERVER_PATH = SERVER_ROOT / "inbound_mail_hub_server.py"
DOC_PATH = ROOT / "docs" / "messaging" / "inbound-mail-hub.md"

sys.path.insert(0, str(SERVER_ROOT))

import inbound_mail_hub

config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
inbound_mail_hub.validate_config(config)
status = inbound_mail_hub.status_payload(config)
assert status["hub"] == "wwcx-inbound-mail-hub"
assert status["state"] == "disabled"
assert status["production_routing_enabled"] is False
assert status["persist_raw_message"] is False
assert status["persist_attachment_bytes"] is False
assert status["unknown_recipient_action"] == "quarantine"

for path in (CORE_PATH, SERVER_PATH, DOC_PATH):
    assert path.is_file(), path
    assert path.stat().st_size > 100, path

server = SERVER_PATH.read_text(encoding="utf-8")
for token in (
    '"/mail-hub/healthz"',
    '"/mail-hub/status"',
    '"/mail-hub/audit"',
    '"/mail-hub/quarantine"',
    '"/mail-hub/ingest"',
    "X-WWCX-Inbound-Token",
    "Refusing non-loopback bind",
):
    assert token in server, token

result = subprocess.run(
    [sys.executable, "-m", "unittest", "tests.test_inbound_mail_hub"],
    cwd=ROOT,
    check=False,
)
assert result.returncode == 0

compile_result = subprocess.run(
    [sys.executable, "-m", "py_compile", str(CORE_PATH), str(SERVER_PATH)],
    cwd=ROOT,
    check=False,
)
assert compile_result.returncode == 0

print("Inbound mail hub validation passed")
print("Production routing, MX changes, SMTP listeners, and message-content persistence remain disabled")
