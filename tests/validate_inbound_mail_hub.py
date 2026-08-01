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

PRIVATE_DESTINATION = "CONFIGURE_PRIVATE_JOHN_MAILBOX"
ROLE_DESTINATION = "CONFIGURE_SHARED_ROLE_MAILBOX"

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
rules = identities["rules"]
assert rules["primary_work_address"] == "john@spiritcreekgardens.com"
assert set(rules["private_john_addresses"]) == {
    "john@ww.cx",
    "john@omegafx.com",
    "john@creekco.ca",
    "john@scgardens.ca",
    "john@spiritcreekgardens.com",
}
assert rules["private_john_delivery_mailbox"] == PRIVATE_DESTINATION
assert rules["shared_role_delivery_mailbox"] == ROLE_DESTINATION
assert rules["private_john_delivery_mailbox"] != rules["shared_role_delivery_mailbox"]
assert rules["require_distinct_private_and_role_destinations"] is True

routes = config["routing"]["routes"]
john_routes = {address: route for address, route in routes.items() if address.startswith("john@")}
role_routes = {address: route for address, route in routes.items() if not address.startswith("john@")}
assert len(john_routes) == 5
assert len(role_routes) == 30
assert all(route["destination"] == PRIVATE_DESTINATION for route in john_routes.values())
assert all(route["destination"] == ROLE_DESTINATION for route in role_routes.values())

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
print("Five private John routes are separated from 30 shared role routes")
print("Private and shared destination placeholders are distinct")
print("Production routing, MX changes, SMTP listeners, and outbound activation remain disabled")
