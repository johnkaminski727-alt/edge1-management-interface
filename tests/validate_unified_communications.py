#!/usr/bin/env python3
"""Validate the WW.CX Unified Communications convergence contract and hub."""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "communications" / "unified-communications.json"
ROOT_INDEX_PATH = ROOT / "src" / "web" / "index.html"
HUB_PATH = ROOT / "src" / "web" / "communications" / "index.html"
STYLE_PATH = ROOT / "src" / "web" / "communications" / "styles.css"
DOC_PATH = ROOT / "docs" / "communications" / "unified-communications-convergence-20260818.md"
AGENT_PATH = ROOT / ".agent" / "unified-communications.md"
CORE_EVENT_PATH = ROOT / "config" / "communications" / "communications-event-v1.json"
IDENTITY_PATH = ROOT / "config" / "communications" / "identity-registry-v1.json"
READINESS_PATH = ROOT / "config" / "communications" / "readiness-matrix-v1.json"
CORE_MODULE_PATH = ROOT / "server" / "unified_communications.py"

for path in (REGISTRY_PATH, ROOT_INDEX_PATH, HUB_PATH, STYLE_PATH, DOC_PATH, AGENT_PATH, CORE_EVENT_PATH, IDENTITY_PATH, READINESS_PATH, CORE_MODULE_PATH):
    assert path.is_file(), path
    assert path.stat().st_size > 100, path

registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
assert registry["contract"] == "wwcx.unified-communications.v1"
assert registry["product"] == "WW.CX Communications"
assert registry["read_only_by_default"] is True
assert registry["production_traffic_authorized"] is False
assert registry["generic_execution_authorized"] is False
assert registry["fresh_edge1_runtime_verified"] is True
channels = registry["channels"]
assert [item["id"] for item in channels] == ["mail", "sms_mms", "voice_sip", "communications_relay"]
for channel in channels:
    assert channel["live_traffic_authorized"] is False
    assert channel["mutation_authorized"] is False
    assert channel["surface"].startswith("/")

by_id = {item["id"]: item for item in channels}
mail = by_id["mail"]["ai_integration"]
assert mail["state"] == "accepted_local_native_read_and_prepare"
assert mail["capabilities"] == [
    "mail.status.read",
    "mail.correspondence.read",
    "mail.draft.prepare",
]
assert mail["provider_pending_capabilities"] == ["mail.correspondence.read.production_native"]
assert mail["live_acceptance"] == "accepted_local_native"
assert mail["production_provider_ready"] is False
assert by_id["sms_mms"]["security_quarantine"] == "security_ready"
sms = by_id["sms_mms"]["ai_integration"]
assert sms["state"] == "accepted_read_only_prepare"
assert sms["capabilities"] == ["messages.status.read", "messages.conversation.read", "messages.draft.prepare"]
assert sms["live_acceptance"] == "accepted"
assert by_id["voice_sip"]["ai_integration"] == {"state": "accepted_read_only", "capabilities": ["telephony.read"]}
assert by_id["communications_relay"]["ai_integration"] == {"state": "accepted_read_only", "capabilities": ["communications.read"]}

assistant = registry["assistant"]
assert assistant["product"] == "WW.CX AI"
assert assistant["edge1_gateway_version"] == "0.3.5-alpha.1"
assert assistant["edge1_mode"] == "read_only"
assert assistant["edge1_listener"] == "127.0.0.1:8787"
assert set(assistant["accepted_live_capabilities"]) == {
    "communications.read",
    "telephony.read",
    "messages.status.read",
    "messages.conversation.read",
    "messages.draft.prepare",
    "mail.status.read",
    "mail.correspondence.read",
    "mail.draft.prepare",
}
assert set(assistant["repository_ready_capabilities"]) == {
    "mail.status.read",
    "mail.draft.prepare",
    "mail.correspondence.read",
}
assert assistant["pending_capabilities"] == []
assert assistant["pending_live_capabilities"] == []
assert assistant["provider_pending_capabilities"] == ["mail.correspondence.read.production_native"]
assert assistant["browser_route"] == "/admin/ai/"
assert assistant["browser_production_acceptance"] == "unverified"
assert all(value is True for value in registry["rules"].values())

core_event = json.loads(CORE_EVENT_PATH.read_text(encoding="utf-8"))
assert core_event["$id"] == "wwcx.communications-event.v1"
assert core_event["properties"]["security"]["properties"]["quarantine_release_authorized"]["const"] is False
identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
assert identity["correlation_policy"]["explicit_evidence_required"] is True
assert identity["correlation_policy"]["name_similarity_is_evidence"] is False
readiness = json.loads(READINESS_PATH.read_text(encoding="utf-8"))
assert readiness["fresh_edge1_runtime_verified"] is True
assert readiness["channels"]["mail"]["live_acceptance"] == "runtime_ready"
assert readiness["channels"]["mail"]["production_authorization"] == "blocked"
assert readiness["channels"]["sms_mms"]["edge1_runtime"] == "runtime_ready"
assert readiness["channels"]["sms_mms"]["security_quarantine"] == "security_ready"
assert readiness["channels"]["private_ai"]["edge1_runtime"] == "runtime_ready"
assert readiness["channels"]["private_ai"]["live_acceptance"] == "runtime_ready"
assert readiness["channels"]["communications_workspace"]["edge1_runtime"] == "runtime_ready"
assert readiness["channels"]["communications_workspace"]["live_acceptance"] == "runtime_ready"
assert readiness["channels"]["communications_workspace"]["production_authorization"] == "blocked"
assert readiness["rules"]["repository_ready_does_not_imply_runtime_ready"] is True
assert readiness["rules"]["runtime_ready_does_not_imply_live_authorized"] is True

root_page = ROOT_INDEX_PATH.read_text(encoding="utf-8")
page = HUB_PATH.read_text(encoding="utf-8")
style = STYLE_PATH.read_text(encoding="utf-8")
assert '<a href="./communications/">Communications</a>' in root_page
for token in ("WW.CX Operations", "Communications", "Mail Room", "SMS &amp; MMS", "Voice &amp; SIP", "News &amp; Relay", "WW.CX AI already understands part of this world.", "communications.read", "telephony.read", "Mail / Correspondence", "Browser acceptance pending", "Read does not mean write", "Draft does not mean send"):
    assert token in page, token
for link in ('href="../outbound-mail/"', 'href="../messaging-operations.html"', 'href="../telephony/"', 'href="../comms-relay/"'):
    assert link in page, link
assert "does not authorize a phone call, SMS/MMS delivery, email send" in page
assert "production browser acceptance is still unverified" in page
assert "@media(max-width:980px)" in style
assert "@media(max-width:700px)" in style
assert "prefers-reduced-motion" in style
for forbidden in ("/send-sms", "/send-mms", "/originate-call", "/reload-dialplan", "/update-trunk", "/change-route"):
    assert forbidden not in page, forbidden

print("Unified Communications convergence validation passed")
print("Fresh accepted Messaging AI: messages.status.read, messages.conversation.read, messages.draft.prepare")
print("Fresh accepted Mail AI: mail.status.read, mail.correspondence.read, mail.draft.prepare")
print("Provider-native Mail remains separately pending and production_provider_ready=false")
print("Historical/fresh accepted read-only AI retained: communications.read, telephony.read")
print("Persistent loopback-only Communications workspace: runtime_ready")
print("Global fresh Edge1 safe-scope runtime verification: true")
print("No production call, message, email, carrier, route, quarantine-release, or generic execution authority added")
