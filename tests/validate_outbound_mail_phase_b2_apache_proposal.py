#!/usr/bin/env python3
"""Static safety validation for the Apache Phase B2 proposal package."""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/messaging/outbound_mail_phase_b2_apache_proposal_audit.sh"
TEMPLATE = ROOT / "deploy/messaging/outbound-mail-preparation-api-apache.conf.example"
RUNBOOK = ROOT / "docs/messaging-operations/outbound-mail-phase-b2-apache-proposal-20260801.md"
STATE = ROOT / ".agent/outbound-mail-b2-readiness.md"

for path in (SCRIPT, TEMPLATE, RUNBOOK, STATE):
    assert path.is_file(), path

text = SCRIPT.read_text(encoding="utf-8")
for value in (
    "set -eu",
    "umask 077",
    "EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}",
    "DISCOVERY_FIX_COMMIT=${DISCOVERY_FIX_COMMIT:-672461ce0f996871be7613a5d6c16bf4950e986d}",
    "PROPOSED_CLIENT_CIDR=${PROPOSED_CLIENT_CIDR:-162.0.217.71/32}",
    "CERTIFICATE_FULLCHAIN_PATH=${CERTIFICATE_FULLCHAIN_PATH:-/etc/letsencrypt/live/edge1.ww.cx/fullchain.pem}",
    "CERTIFICATE_PRIVATE_KEY_PATH=${CERTIFICATE_PRIVATE_KEY_PATH:-/etc/letsencrypt/live/edge1.ww.cx/privkey.pem}",
    "ACTIVE_VHOST=${ACTIVE_VHOST:-/etc/apache2/sites-enabled/edge1.ww.cx.conf}",
    "outbound-mail-phase-b2-apache-proposal",
    "git status --porcelain --untracked-files=all",
    "git merge-base --is-ancestor",
    "127.0.0.1:$PORT",
    "/outbound-mail/healthz",
    "unsigned preparation status did not return HTTP 401",
    "send probe did not return HTTP 403",
    "apache2.service",
    "proxy.load proxy_http.load authz_core.load authz_host.load ssl.load",
    "active edge1 Apache vhost is not an enabled-site symlink",
    "fullchain_reference_count",
    "private_key_reference_count",
    "an Apache configuration already references the preparation API path",
    "/etc/letsencrypt/live/edge1.ww.cx/fullchain.pem",
    "/etc/letsencrypt/live/edge1.ww.cx/privkey.pem",
    "/etc/letsencrypt/archive/edge1.ww.cx/fullchain*.pem",
    "/etc/letsencrypt/archive/edge1.ww.cx/privkey*.pem",
    "stat -Lc",
    "contents_read=no",
    "certificate_private_key_contents_read no",
    "certificate_key_pair_match_deferred_to_install yes",
    "candidate-apache-fragment.conf",
    "ready_for_explicit_b2_apache_authorization",
    "hmac_secret_read no",
    "proxy_config_installed no",
    "proxy_service_reloaded no",
    "certificate_generated no",
    "dns_modified no",
    "firewall_modified no",
    "public_listener_added no",
    "website_bridge_enabled no",
    "provider_or_sender_enabled no",
    "external_delivery_enabled no",
    "message_sent no",
    "SHA256SUMS",
):
    assert value in text, value

for value in (
    "systemctl restart",
    "systemctl reload",
    "systemctl try-restart",
    "systemctl start",
    "systemctl stop",
    "a2enconf",
    "a2ensite",
    "apache2ctl graceful",
    "apachectl graceful",
    "certbot",
    "acme.sh",
    "openssl pkey",
    "openssl rsa",
    "openssl ec",
    "openssl pkcs8",
    'cat "$CERTIFICATE_PRIVATE_KEY_PATH"',
    'sha256sum "$CERTIFICATE_PRIVATE_KEY_PATH"',
    "nft add",
    "nft delete",
    "iptables -A",
    "iptables -I",
    "iptables -D",
    "ufw allow",
    "ufw deny",
    "WWCX_MAIL_GATEWAY_TOKEN=",
):
    assert value not in text, value

assert text.count("record message_sent no") == 1
assert text.index("git status --porcelain --untracked-files=all") < text.index("install -d -m 0700")
assert text.index("certificate_private_key_contents_read no") > text.index("certificate-private-key-path-metadata.txt")
assert text.index("proxy_config_installed no") > text.index("candidate-apache-fragment.conf")

syntax = subprocess.run(["sh", "-n", str(SCRIPT)], cwd=ROOT, check=False)
assert syntax.returncode == 0

template = TEMPLATE.read_text(encoding="utf-8")
for value in (
    "PREPARATION_API_HOSTNAME",
    "PREPARATION_CLIENT_CIDR",
    "CERTIFICATE_FULLCHAIN_PATH",
    "CERTIFICATE_PRIVATE_KEY_PATH",
    '<LocationMatch "^/outbound-mail/api/v1/status$">',
    '<LocationMatch "^/outbound-mail/api/v1/prepare$">',
    "<Limit GET>",
    "<Limit POST>",
    "<LimitExcept GET>",
    "<LimitExcept POST>",
    "Require all denied",
    "ProxyPass",
    "ProxyPassReverse",
    "http://127.0.0.1:8104/outbound-mail/api/v1/status",
    "http://127.0.0.1:8104/outbound-mail/api/v1/prepare",
):
    assert value in template, value
assert template.count("Require ip PREPARATION_CLIENT_CIDR") == 2
assert template.count('<LocationMatch "^/outbound-mail/api/v1/status$">') == 1
assert template.count('<LocationMatch "^/outbound-mail/api/v1/prepare$">') == 1
assert "/outbound-mail/send" not in template
assert 'LocationMatch "^/outbound-mail/api/v1/.*' not in template

runbook = RUNBOOK.read_text(encoding="utf-8")
for value in (
    "20260801T204148Z",
    "active_edge1_vhost_count=2",
    "fullchain_reference_count=1",
    "private_key_reference_count=1",
    "Apache 2",
    "Let's Encrypt",
    "live-to-archive symlink chain",
    "does not read private-key contents",
    "ready_for_explicit_b2_apache_authorization",
    "No live Apache change",
):
    assert value in runbook, value

state = STATE.read_text(encoding="utf-8")
for value in (
    "2026-08-01T20:41:48Z",
    "20260801T204148Z",
    "ready_for_phase_b2_proposal_validation",
    "Apache-specific proposal package",
    "public preparation route: **not yet activated**",
    "production message: **not defined or sent**",
):
    assert value in state, value

print("Outbound mail Phase B2 Apache proposal validation passed")
print("The standard Let's Encrypt live-to-archive symlink chain is metadata-validated")
print("Private-key contents, Apache runtime state, delivery, and messages remain untouched")
