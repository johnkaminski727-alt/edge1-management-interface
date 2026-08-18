#!/usr/bin/env python3
"""Validate the WW.CX Unified Communications convergence contract and hub."""

from __future__ import annotations

import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "communications" / "unified-communications.json"
HUB_PATH = ROOT / "src" / "web" / "communications" / "index.html"
STYLE_PATH = ROOT / "src" / "web" / "communications" / "styles.css"
DOC_PATH = ROOT / "docs" / "communications" / "unified-communications-convergence-20260818.md"
AGENT_PATH = ROOT / ".agent" / "unified-communications.md"

for path in (REGISTRY_PATH, HUB_PATH, STYLE_PATH, DOC_PATH, AGENT_PATH):
    assert path.is_file(), path
    assert path.stat().st_size > 100, path

registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
assert registry["contract"] == "wwcx.unified-communications.v1"
assert registry["product"] == "WW.CX Communications"
assert registry["read_only_by_default"] is True
assert registry["production_traffic_authorized"] is False
assert registry["generic_execution_authorized"] is False

channels = registry["channels"]
assert [item["id"] for item in channels] == [
    "mail",
    "sms_mms",
    "voice_sip",
    "communications_relay",
]

for channel in channels:
    assert channel["live_traffic_authorized"] is False, channel["id"]
    assert channel["mutation_authorized"] is False, channel["id"]
    assert channel["surface"].startswith("/"), channel["id"]

by_id = {item["id"]: item for item in channels}
assert by_id["mail"]["current_mode"] == "prepare_only"
assert by_id["mail"]["ai_integration"]["state"] == "planned"
assert by_id["mail"]["ai_integration"]["capabilities"] == [
    "mail.status.read",
    "mail.correspondence.read",
    "mail.draft.prepare",
]
assert by_id["sms_mms"]["current_mode"] == "operations_and_simulator"
assert by_id["sms_mms"]["ai_integration"]["state"] == "not_yet_integrated"
assert by_id["voice_sip"]["ai_integration"] == {
    "state": "accepted_read_only",
    "capabilities": ["telephony.read"],
}
assert by_id["communications_relay"]["ai_integration"] == {
    "state": "accepted_read_only",
    "capabilities": ["communications.read"],
}

assistant = registry["assistant"]
assert assistant["product"] == "WW.CX AI"
assert assistant["edge1_gateway_version"] == "0.3.4-alpha.2"
assert assistant["edge1_mode"] == "read_only"
assert assistant["edge1_listener"] == "127.0.0.1:8787"
assert set(assistant["accepted_capabilities"]) == {"communications.read", "telephony.read"}
assert assistant["browser_route"] == "/admin/ai/"
assert assistant["browser_production_acceptance"] == "unverified"

rules = registry["rules"]
assert all(value is True for value in rules.values())

page = HUB_PATH.read_text(encoding="utf-8")
style = STYLE_PATH.read_text(encoding="utf-8")
for token in (
    "WW.CX Operations",
    "Communications",
    "Mail Room",
    "SMS &amp; MMS",
    "Voice &amp; SIP",
    "News &amp; Relay",
    "WW.CX AI already understands part of this world.",
    "communications.read",
    "telephony.read",
    "Mail / Correspondence",
    "Browser acceptance pending",
    "Read does not mean write",
    "Draft does not mean send",
):
    assert token in page, token

for link in (
    'href="../outbound-mail/"',
    'href="../messaging-operations.html"',
    'href="../telephony/"',
    'href="../comms-relay/"',
):
    assert link in page, link

assert "does not authorize a phone call, SMS/MMS delivery, email send" in page
assert "production browser acceptance is still unverified" in page
assert "@media(max-width:980px)" in style
assert "@media(max-width:700px)" in style
assert "prefers-reduced-motion" in style

# The convergence surface is navigation/readiness only. It must not grow
# direct provider or telephony mutation endpoints by accident.
for forbidden in (
    "/send-sms",
    "/send-mms",
    "/originate-call",
    "/reload-dialplan",
    "/update-trunk",
    "/change-route",
):
    assert forbidden not in page, forbidden

print("Unified Communications convergence validation passed")
print("Channels: Mail Room, SMS/MMS, Voice/SIP, News/Relay")
print("Accepted AI reads: communications.read, telephony.read")
print("Mail AI scopes remain planned; SMS/MMS AI integration remains future work")
print("No production call, message, email, carrier, route, or generic execution authority added")
