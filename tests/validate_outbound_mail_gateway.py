#!/usr/bin/env python3
"""Repository validation for the disabled identity-aware outbound-mail gateway."""

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
IDENTITIES_PATH = ROOT / "config" / "messaging" / "mail-identities.json"
PAGE_PATH = ROOT / "src" / "web" / "outbound-mail" / "index.html"
SCRIPT_PATH = ROOT / "src" / "web" / "outbound-mail" / "app.js"
STYLE_PATH = ROOT / "src" / "web" / "outbound-mail" / "styles.css"
SERVER_PATH = ROOT / "server" / "outbound_mail_gateway_server.py"
IDENTITY_PATH = ROOT / "server" / "mail_identity_registry.py"
FACADE_PATH = ROOT / "server" / "identity_aware_outbound_gateway.py"
AUTH_PATH = ROOT / "server" / "outbound_mail_preparation_auth.py"

sys.path.insert(0, str(SERVER_ROOT))

import identity_aware_outbound_gateway
import mail_identity_registry
import outbound_mail_gateway
import outbound_mail_policy


config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
identities = json.loads(IDENTITIES_PATH.read_text(encoding="utf-8"))
outbound_mail_gateway.validate_gateway_config(config)
outbound_mail_policy.validate_policy(policy)
mail_identity_registry.validate_registry(identities)

status = identity_aware_outbound_gateway.status_payload(config, policy, identities)
assert status["gateway"] == "wwcx-outbound-mail-gateway"
assert status["preview_enabled"] is True
assert status["external_delivery_enabled"] is False
assert status["hidden_open_tracking"] is False
assert status["device_fingerprinting"] is False
assert status["persist_message_bodies"] is False
assert status["persist_attachment_bytes"] is False
assert status["preparation_api"]["enabled"] is False
assert status["preparation_api"]["authentication"] == "hmac_sha256"
assert status["preparation_api"]["runtime_secret_configured"] is False
selection_status = status["sender_selection"]
assert selection_status["automatic_selection_enabled"] is True
assert selection_status["allow_submitted_from_override"] is False
assert selection_status["private_delivery_mailbox"] == "john-inbox@ww.cx"
assert selection_status["shared_delivery_mailbox"] == "maildesk@ww.cx"
assert selection_status["system_sender"] == "noreply@ww.cx"
assert selection_status["outbound_activation_authorized"] is False
assert selection_status["live_sender_count"] == 0
assert selection_status["managed_domains"] == sorted(identities["domains"])

preview = identity_aware_outbound_gateway.compose_preview(
    config,
    policy,
    identities,
    {
        "from_address": "untrusted@example.com",
        "reply_to": "untrusted@example.com",
        "original_recipient": "john@spiritcreekgardens.com",
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
assert preview["request"]["from_address"] == "john@spiritcreekgardens.com"
assert preview["request"]["reply_to"] == "john@spiritcreekgardens.com"
assert preview["sender_selection"]["reason"] == "original_recipient"
assert preview["sender_selection"]["from_address_replaced"] is True
assert "untrusted@example.com" not in json.dumps(preview)

system_preview = identity_aware_outbound_gateway.compose_preview(
    config,
    policy,
    identities,
    {
        "system_generated": True,
        "to": "recipient@example.com",
        "subject": "System preview validation",
        "body": "This system message is previewed but not sent.",
        "message_class": "business_correspondence",
        "mailing_address": "151 2 Street South, Invermay, SK",
    },
)
assert system_preview["request"]["from_address"] == "noreply@ww.cx"
assert system_preview["request"]["reply_to"] is None
assert system_preview["sender_selection"]["reason"] == "system_generated"
assert system_preview["sender_selection"]["live_enabled"] is False

for path in (
    PAGE_PATH,
    SCRIPT_PATH,
    STYLE_PATH,
    SERVER_PATH,
    IDENTITY_PATH,
    FACADE_PATH,
    AUTH_PATH,
    IDENTITIES_PATH,
):
    assert path.is_file(), path
    assert path.stat().st_size > 100, path

page = PAGE_PATH.read_text(encoding="utf-8")
script = SCRIPT_PATH.read_text(encoding="utf-8")
server = SERVER_PATH.read_text(encoding="utf-8")
for required in (
    "Mail Room",
    "Write a message",
    "Review final message",
    "Find correspondence quickly",
    'data-panel="setup"',
    'data-panel="compose"',
    'data-panel="controls"',
    'data-panel="preview"',
    'data-panel="activity"',
    "Hidden open-tracking pixel",
    "Device fingerprinting",
    'id="submit-message" disabled',
    'id="original-recipient"',
    'id="system-generated"',
    "john-inbox@ww.cx",
    "maildesk@ww.cx",
    "noreply@ww.cx",
):
    assert required in page, required
for required in (
    "/outbound-mail/status",
    "/outbound-mail/preview",
    "/outbound-mail/send",
    "/outbound-mail/audit",
    "no-hidden-pixel",
    "confirm_send",
    "original_recipient",
    "identity_hint",
    "system_generated",
    "sender_selection",
    "managed_domains",
    "invalidatePreview",
    "noreply@ww.cx",
):
    assert required in script, required
for required in (
    '"/outbound-mail/app.js"',
    '"/outbound-mail/styles.css"',
    '"/outbound-mail/status"',
    '"/outbound-mail/preview"',
    '"/outbound-mail/send"',
    '"/outbound-mail/api/v1/status"',
    '"/outbound-mail/api/v1/prepare"',
    "preparation_auth.verify_request",
    "outbound_message_prepared_api",
    "DEFAULT_IDENTITIES",
    "identity_gateway.compose_preview",
    "identity_gateway.send_message",
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
        "tests.test_mail_identity_registry",
        "tests.test_identity_aware_outbound_gateway",
        "tests.test_outbound_mail_preparation_auth",
    ],
    cwd=ROOT,
    check=False,
)
assert unit_result.returncode == 0

compile_result = subprocess.run(
    [
        sys.executable,
        "-m",
        "py_compile",
        str(SERVER_PATH),
        str(IDENTITY_PATH),
        str(FACADE_PATH),
        str(AUTH_PATH),
    ],
    cwd=ROOT,
    check=False,
)
assert compile_result.returncode == 0

node = shutil.which("node")
if node:
    node_result = subprocess.run([node, "--check", str(SCRIPT_PATH)], check=False)
    assert node_result.returncode == 0

print("Identity-aware Mail Room gateway validation passed")
print("Private delivery mailbox: john-inbox@ww.cx")
print("Shared role delivery mailbox: maildesk@ww.cx")
print("System sender: noreply@ww.cx")
print("Submitted From and Reply-To values are replaced by registered identities")
print("External delivery and every live sender remain disabled")
