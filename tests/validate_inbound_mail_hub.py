#!/usr/bin/env python3
"""Repository validation for the disabled multi-domain inbound mail hub."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
CONFIG_PATH = ROOT / "config" / "messaging" / "inbound-mail-hub.json"
IDENTITIES_PATH = ROOT / "config" / "messaging" / "mail-identities.json"
CORE_PATH = SERVER_ROOT / "inbound_mail_hub.py"
SERVER_PATH = SERVER_ROOT / "inbound_mail_hub_server.py"
DOC_PATH = ROOT / "docs" / "messaging" / "inbound-mail-hub.md"

sys.path.insert(0, str(SERVER_ROOT))

import inbound_mail_hub

config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
identities = json.loads(IDENTITIES_PATH.read_text(encoding="utf-8"))
inbound_mail_hub.validate_config(config)
status = inbound_mail_hub.status_payload(config)
assert status["hub"] == "wwcx-inbound-mail-hub"
assert status["state"] == "disabled"
assert status["production_routing_enabled"] is False
assert status["persist_raw_message"] is False
assert status["persist_attachment_bytes"] is False
assert status["unknown_recipient_action"] == "quarantine"
assert set(status["domains"]) == {
    "ww.cx",
    "creekco.ca",
    "spiritcreekgardens.com",
    "scgardens.ca",
    "omegafx.com",
}
assert status["route_count"] == 35
assert identities["outbound_activation_authorized"] is False
assert identities["rules"]["primary_work_address"] == "john@spiritcreekgardens.com"
assert set(identities["rules"]["personal_aliases"]) == {
    "john@ww.cx",
    "john@omegafx.com",
    "john@creekco.ca",
    "john@scgardens.ca",
}

for path in (CORE_PATH, SERVER_PATH, DOC_PATH, IDENTITIES_PATH):
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
print("Five managed domains and 35 named routes validated")
print("Personal John aliases and Spirit Creek Gardens work identity validated")
print("Production routing, MX changes, SMTP listeners, and outbound activation remain disabled")
