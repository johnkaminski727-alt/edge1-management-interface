#!/usr/bin/env python3
"""Repository validation for the disabled WW.CX outbound-mail gateway."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
CONFIG_PATH = ROOT / "config" / "messaging" / "outbound-mail-gateway.json"
POLICY_PATH = ROOT / "config" / "messaging" / "outbound-mail-policy.json"
PAGE_PATH = ROOT / "src" / "web" / "outbound-mail-gateway.html"

sys.path.insert(0, str(SERVER_ROOT))

import outbound_mail_gateway
import outbound_mail_policy


config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
outbound_mail_gateway.validate_gateway_config(config)
outbound_mail_policy.validate_policy(policy)

status = outbound_mail_gateway.status_payload(config, policy)
assert status["gateway"] == "wwcx-outbound-mail-gateway"
assert status["preview_enabled"] is True
assert status["external_delivery_enabled"] is False
assert status["hidden_open_tracking"] is False
assert status["device_fingerprinting"] is False
assert status["persist_message_bodies"] is False
assert status["persist_attachment_bytes"] is False

preview = outbound_mail_gateway.compose_preview(
    config,
    policy,
    {
        "from_address": "john@ww.cx",
        "to": "recipient@example.com",
        "subject": "Controlled preview validation",
        "body": "This is a repository validation message. No external delivery occurs.",
        "message_class": "business_correspondence",
        "signer_name": "John Kaminski",
        "signer_title": "Authorized Representative",
        "case_id": "TEST-MATTER-001",
        "action_id": "TEST-ACTION-001",
        "mailing_address": "151 2 Street South, Invermay, SK",
    },
)
assert outbound_mail_policy.FOOTER_MARKER in preview["body"]
assert "Access to the linked correspondence record may be logged" in preview["body"]
assert "does not create confidentiality, privilege" in preview["body"]
assert preview["headers"]["X-WWCX-Tracking"] == "disclosed-action-link; no-hidden-pixel"
assert len(preview["action_token_sha256"]) == 64
assert preview["action_token"] not in json.dumps(preview["audit_record"])

assert PAGE_PATH.is_file()
page = PAGE_PATH.read_text(encoding="utf-8")
for required in (
    "Outbound Mail Gateway",
    "/outbound-mail/status",
    "/outbound-mail/preview",
    "/outbound-mail/send",
    "/outbound-mail/audit",
    "Generate controlled preview",
    "Hidden open tracking",
    "Device fingerprinting",
    "Audit and action matrix",
):
    assert required in page, required
assert "send-button" in page
assert "disabled>Send through gateway" in page

result = subprocess.run(
    [
        sys.executable,
        "-m",
        "unittest",
        "tests.test_outbound_mail_policy",
        "tests.test_outbound_mail_gateway",
    ],
    cwd=ROOT,
    check=False,
)
assert result.returncode == 0

print("Outbound mail gateway validation passed")
print("Admin preview available; external delivery remains disabled")
