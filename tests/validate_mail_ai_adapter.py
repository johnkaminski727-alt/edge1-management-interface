#!/usr/bin/env python3
"""Repository validation for bounded Mail Room Private AI capabilities."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import mail_ai_adapter


def sample_request() -> dict:
    return {
        "from_address": "wrong@example.net",
        "identity_hint": "creekco-contact",
        "to": ["records@example.com"],
        "cc": [],
        "bcc": [],
        "subject": "AI-prepared records follow-up",
        "body": "Hello,\n\nPlease provide the requested records.\n",
        "message_class": "business_correspondence",
        "signer_name": "John Kaminski",
        "signer_title": "Authorized Representative",
        "case_id": "TEST-AI-MAIL-001",
        "action_id": "TEST-AI-ACTION-001",
        "mailing_address": "151 2 Street South, Invermay, SK",
    }


status = mail_ai_adapter.status()
assert status["contract"] == "wwcx.mail-ai-status.v1"
assert status["capabilities"] == ["mail.status.read", "mail.draft.prepare"]
assert status["pending_capabilities"] == ["mail.correspondence.read"]
assert status["correspondence"]["state"] == "blocked_configuration_disabled"
assert status["correspondence"]["production_provider_ready"] is False
assert status["send_authorized"] is False
assert status["mutation_authorized"] is False
assert "password" not in str(status).casefold()
assert "credential" not in str(status).casefold()

draft = mail_ai_adapter.prepare_draft(sample_request())
assert draft["contract"] == "wwcx.mail-ai-draft.v1"
assert draft["state"] == "drafted"
assert draft["ai_generated"] is True
assert draft["delivery_status"] == "prepared_not_sent"
assert draft["network_activity"] is False
assert draft["external_delivery_attempted"] is False
assert draft["send_authorized"] is False
assert draft["mutation_authorized"] is False
assert "action_token" not in draft["draft"]
assert draft["draft"]["sender_selection"]["address"] == "contact@creekco.ca"
assert draft["draft"]["request"]["from_address"] == "contact@creekco.ca"
assert "AI-prepared records follow-up" in draft["draft"]["request"]["subject"]

correspondence = mail_ai_adapter.correspondence_read_state()
assert correspondence["capability"] == "mail.correspondence.read"
assert correspondence["state"] == "blocked_configuration_disabled"
assert correspondence["read_enabled"] is False
assert correspondence["production_provider_ready"] is False
assert correspondence["mutation_authorized"] is False
assert correspondence["send_authorized"] is False

source = (SERVER / "mail_ai_adapter.py").read_text(encoding="utf-8")
for forbidden in ("smtplib", "send_message(", ".send(", "requests.", "urllib.request"):
    assert forbidden not in source, forbidden

print("Mail Room Private AI adapter validation passed")
print("Default capabilities: mail.status.read, mail.draft.prepare")
print("mail.correspondence.read remains disabled unless a private authoritative store is enabled")
print("No network, send, provider, or mutation authority added to the adapter")
