#!/usr/bin/env python3
"""Repository validation for the disabled WW.CX outbound-mail gateway."""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
CONFIG_PATH = ROOT / "config" / "messaging" / "outbound-mail-gateway.json"
POLICY_PATH = ROOT / "config" / "messaging" / "outbound-mail-policy.json"
PAGE_PATH = ROOT / "src" / "web" / "outbound-mail" / "index.html"
SCRIPT_PATH = ROOT / "src" / "web" / "outbound-mail" / "app.js"
STYLE_PATH = ROOT / "src" / "web" / "outbound-mail" / "styles.css"
SERVER_PATH = ROOT / "server" / "outbound_mail_gateway_server.py"

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

for path in (PAGE_PATH, SCRIPT_PATH, STYLE_PATH, SERVER_PATH):
    assert path.is_file(), path
    assert path.stat().st_size > 100, path

page = PAGE_PATH.read_text(encoding="utf-8")
script = SCRIPT_PATH.read_text(encoding="utf-8")
server = SERVER_PATH.read_text(encoding="utf-8")
for required in (
    "Outbound Mail Gateway",
    'data-panel="setup"',
    'data-panel="compose"',
    'data-panel="controls"',
    'data-panel="preview"',
    'data-panel="activity"',
    "Hidden open-tracking pixel",
    "Device fingerprinting",
    "Correspondence matrix",
    'id="submit-message" disabled',
):
    assert required in page, required
for required in (
    "/outbound-mail/status",
    "/outbound-mail/preview",
    "/outbound-mail/send",
    "/outbound-mail/audit",
    "no-hidden-pixel",
    "confirm_send",
):
    assert required in script, required
for required in (
    '"/outbound-mail/app.js"',
    '"/outbound-mail/styles.css"',
    '"/outbound-mail/status"',
    '"/outbound-mail/preview"',
    '"/outbound-mail/send"',
):
    assert required in server, required

unit_result = subprocess.run(
    [
        sys.executable,
        "-m",
        "unittest",
        "tests.test_outbound_mail_policy",
        "tests.test_outbound_mail_gateway",
        "tests.test_outbound_mail_admin_assets",
    ],
    cwd=ROOT,
    check=False,
)
assert unit_result.returncode == 0

node = shutil.which("node")
if node:
    node_result = subprocess.run([node, "--check", str(SCRIPT_PATH)], check=False)
    assert node_result.returncode == 0

print("Outbound mail gateway validation passed")
print("Canonical admin wizard uses the gateway API; external delivery remains disabled")
