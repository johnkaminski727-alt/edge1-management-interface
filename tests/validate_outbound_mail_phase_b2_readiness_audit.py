#!/usr/bin/env python3
"""Static safety validation for the read-only outbound mail Phase B2 audit."""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/messaging/outbound_mail_phase_b2_readiness_audit.sh"
RUNBOOK = ROOT / "docs/messaging-operations/outbound-mail-phase-b2-readiness-audit-20260801.md"
STATE = ROOT / ".agent/outbound-mail-b2-readiness.md"
TEMPLATE = ROOT / "deploy/messaging/outbound-mail-preparation-api-nginx.conf.example"

for path in (SCRIPT, RUNBOOK, STATE, TEMPLATE):
    assert path.is_file(), path

text = SCRIPT.read_text(encoding="utf-8")
required = (
    "set -eu",
    "umask 077",
    "EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}",
    "B1_LIVE_ACCEPTANCE_COMMIT=${B1_LIVE_ACCEPTANCE_COMMIT:-53bb0ea15cdedb136add858841813273252cc8fc}",
    "B2_BASELINE_COMMIT=${B2_BASELINE_COMMIT:-f1f65571902c7f377c6a7ca9c52f634973a7635a}",
    "PROPOSED_HOSTNAME=${PROPOSED_HOSTNAME:-}",
    "PROPOSED_CLIENT_CIDR=${PROPOSED_CLIENT_CIDR:-}",
    "CERTIFICATE_FULLCHAIN_PATH=${CERTIFICATE_FULLCHAIN_PATH:-}",
    "CERTIFICATE_PRIVATE_KEY_PATH=${CERTIFICATE_PRIVATE_KEY_PATH:-}",
    "EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-readiness",
    "install -d -m 0700 \"$output_dir\"",
    "status --porcelain --untracked-files=all",
    "merge-base --is-ancestor",
    "protected B2 files changed after the approved baseline",
    "outbound-mail-preparation-api-nginx.conf.example",
    "location = /outbound-mail/api/v1/status",
    "location = /outbound-mail/api/v1/prepare",
    "send_route_present",
    "systemctl is-active --quiet",
    "systemctl is-enabled --quiet",
    "127.0.0.1:8104",
    "unsigned preparation API status did not return HTTP 401",
    "send probe did not return HTTP 403",
    'status["preparation_api"]["enabled"] is True',
    'status["preparation_api"]["runtime_secret_configured"] is True',
    'status["external_delivery_enabled"] is False',
    'status["policy_enabled"] is False',
    'status["sender_selection"]["live_sender_count"] == 0',
    "check_runtime_file /etc/wwcx/outbound-mail-gateway.env 600",
    "proxy-path-matches.txt",
    "port-443-listeners.txt",
    "nft list ruleset",
    "iptables-save",
    "ip6tables-save",
    "ufw status verbose",
    "client source must be one exact IPv4 /32 or IPv6 /128 address",
    "openssl x509",
    "certificate private-key path mode must be 0400 or 0600",
    "contents_read=no",
    "candidate-nginx.conf",
    "awaiting_explicit_b2_parameters",
    "awaiting_separately_authorized_dns_or_parameter_resolution",
    "ready_for_explicit_b2_authorization",
    "hmac_secret_read no",
    "certificate_private_key_read no",
    "proxy_config_installed no",
    "proxy_service_reloaded no",
    "certificate_generated no",
    "dns_modified no",
    "firewall_modified no",
    "public_listener_added no",
    "website_bridge_enabled no",
    "provider_or_sender_enabled no",
    "message_sent no",
    "SHA256SUMS",
)
for value in required:
    assert value in text, value

prohibited = (
    "systemctl restart",
    "systemctl reload",
    "systemctl try-restart",
    "systemctl start",
    "systemctl stop",
    "nginx -s",
    "apachectl graceful",
    "caddy reload",
    "certbot",
    "acme.sh",
    "openssl req",
    "openssl pkey",
    "openssl rsa",
    "nft add",
    "nft delete",
    "nft insert",
    "iptables -A",
    "iptables -I",
    "iptables -D",
    "ip6tables -A",
    "ufw allow",
    "ufw deny",
    "firewall-cmd --add",
    "firewall-cmd --remove",
    'cat "$CERTIFICATE_PRIVATE_KEY_PATH"',
    'sha256sum "$CERTIFICATE_PRIVATE_KEY_PATH"',
    'cat /etc/wwcx/outbound-mail-gateway.env',
    'source /etc/wwcx/outbound-mail-gateway.env',
    '. /etc/wwcx/outbound-mail-gateway.env',
    "WWCX_MAIL_GATEWAY_TOKEN=",
    "/etc/nginx/sites-enabled/outbound",
    "/etc/nginx/conf.d/outbound",
)
for value in prohibited:
    assert value not in text, value

assert text.count('record message_sent no') == 1
assert text.index("protected B2 files changed after the approved baseline") < text.index("supplied_count=0")
assert text.index('status["preparation_api"]["runtime_secret_configured"] is True') < text.index("supplied_count=0")
assert text.index("certificate_private_key_read no") > text.index("candidate-nginx.conf")

syntax = subprocess.run(["sh", "-n", str(SCRIPT)], cwd=ROOT, check=False)
assert syntax.returncode == 0

template = TEMPLATE.read_text(encoding="utf-8")
assert template.count("location = /outbound-mail/api/v1/status") == 1
assert template.count("location = /outbound-mail/api/v1/prepare") == 1
assert "/outbound-mail/send" not in template
assert "proxy_pass http://127.0.0.1:8104" in template
assert "allow PREPARATION_CLIENT_CIDR" in template
assert "deny all" in template
assert "client_max_body_size 320k" in template
assert "ssl_protocols TLSv1.2 TLSv1.3" in template
assert "return 404" in template

runbook = RUNBOOK.read_text(encoding="utf-8")
for value in (
    "readiness_state=awaiting_explicit_b2_parameters",
    "PROPOSED_HOSTNAME",
    "PROPOSED_CLIENT_CIDR",
    "CERTIFICATE_FULLCHAIN_PATH",
    "CERTIFICATE_PRIVATE_KEY_PATH",
    "The values above are format examples only",
    "does not parse, validate, hash, print, or otherwise read the private-key contents",
    "ready_for_explicit_b2_authorization",
    "No rule is added, removed, enabled, or reloaded",
    "Separate B2 authorization still required",
    "Stop before",
):
    assert value in runbook, value

state = STATE.read_text(encoding="utf-8")
for value in (
    "Phase B1 is accepted live",
    "B2 audit execution: **not yet executed**",
    "certificate/private-key access authorized: **no**",
    "proxy installation or reload authorized: **no**",
    "DNS change authorized: **no**",
    "firewall change authorized: **no**",
    "production message authorized: **no**",
    "A generic `Continue` does not authorize those privileged actions",
):
    assert value in state, value

print("Outbound mail Phase B2 read-only readiness audit validation passed")
print("Baseline and proposal modes remain non-mutating")
print("HMAC and certificate private-key contents remain unread")
print("Proxy, certificate, DNS, firewall, website, provider, sender, and delivery changes remain gated")
