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
IDENTITY_ENGINE_PATH = SERVER_ROOT / "mail_identity_registry.py"
DOC_PATH = ROOT / "docs" / "messaging" / "inbound-mail-hub.md"

sys.path.insert(0, str(SERVER_ROOT))

import inbound_mail_hub
import mail_identity_registry

PRIVATE_DESTINATION = "john-inbox@ww.cx"
ROLE_DESTINATION = "maildesk@ww.cx"
SYSTEM_SENDER = "noreply@ww.cx"

config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
identities = json.loads(IDENTITIES_PATH.read_text(encoding="utf-8"))
inbound_mail_hub.validate_config(config)
mail_identity_registry.validate_registry(identities)
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

rules = identities["rules"]
assert identities["contract"] == "wwcx.mail-identities.v2"
assert identities["outbound_activation_authorized"] is False
assert rules["primary_work_address"] == "john@spiritcreekgardens.com"
assert rules["private_john_delivery_mailbox"] == PRIVATE_DESTINATION
assert rules["shared_role_delivery_mailbox"] == ROLE_DESTINATION
assert rules["system_sender"] == SYSTEM_SENDER
assert len({PRIVATE_DESTINATION, ROLE_DESTINATION, SYSTEM_SENDER}) == 3
assert identities["mailboxes"]["private_john"]["accepts_direct_public_use"] is False
assert identities["mailboxes"]["shared_role"]["accepts_direct_public_use"] is False

routes = config["routing"]["routes"]
john_routes = {address: route for address, route in routes.items() if address.startswith("john@")}
role_routes = {address: route for address, route in routes.items() if not address.startswith("john@")}
assert len(john_routes) == 5
assert len(role_routes) == 30
assert all(route["destination"] == PRIVATE_DESTINATION for route in john_routes.values())
assert all(route["destination"] == ROLE_DESTINATION for route in role_routes.values())
assert PRIVATE_DESTINATION not in routes
assert ROLE_DESTINATION not in routes
assert SYSTEM_SENDER not in routes

for path in (CORE_PATH, SERVER_PATH, IDENTITY_ENGINE_PATH, DOC_PATH, IDENTITIES_PATH):
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
    [
        sys.executable,
        "-m",
        "py_compile",
        str(CORE_PATH),
        str(SERVER_PATH),
        str(IDENTITY_ENGINE_PATH),
    ],
    cwd=ROOT,
    check=False,
)
assert compile_result.returncode == 0

print("Inbound mail hub validation passed")
print("Five private John routes deliver to john-inbox@ww.cx")
print("Thirty shared role routes deliver to maildesk@ww.cx")
print("noreply@ww.cx is reserved as an outbound-only system identity")
print("Production routing, MX changes, SMTP listeners, and outbound activation remain disabled")
