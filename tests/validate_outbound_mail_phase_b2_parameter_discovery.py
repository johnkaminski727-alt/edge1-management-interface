#!/usr/bin/env python3
"""Static safety validation for Phase B2 parameter discovery."""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/messaging/outbound_mail_phase_b2_parameter_discovery.sh"
RUNBOOK = ROOT / "docs/messaging-operations/outbound-mail-phase-b2-parameter-discovery-20260801.md"

for path in (SCRIPT, RUNBOOK):
    assert path.is_file(), path

text = SCRIPT.read_text(encoding="utf-8")
for value in (
    "set -eu",
    "umask 077",
    "EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}",
    "PROPOSED_HOSTNAME=${PROPOSED_HOSTNAME:-edge1.ww.cx}",
    "PROPOSED_CLIENT_CIDR=${PROPOSED_CLIENT_CIDR:-}",
    "HEALTH_PATH=${HEALTH_PATH:-/outbound-mail/healthz}",
    "outbound-mail-phase-b2-parameter-discovery",
    "install -d -m 0700",
    "git status --porcelain --untracked-files=all",
    "127.0.0.1:$PORT",
    "health_http",
    "unsigned_api_status_http",
    "send_probe_http",
    "active-edge1-vhosts.txt",
    "active-edge1-certificate-references.txt",
    "active-certificate-paths.txt",
    "active-private-key-paths.txt",
    "active-certificate-metadata.txt",
    "active-private-key-path-metadata.txt",
    "active_tls_pair_in_enabled_vhost",
    "proxy-certificate-references.txt",
    "certificate-candidates.txt",
    "private-key-path-metadata.txt",
    "contents_read=no",
    "candidate-parameters.env",
    "BUSINESS159_EGRESS_MEASUREMENT_REQUIRED",
    "ready_for_phase_b2_proposal_validation",
    "awaiting_business159_egress_measurement",
    "awaiting_active_certificate_selection_and_business159_egress_measurement",
    "private_key_contents_read no",
    "hmac_secret_read no",
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
):
    assert value in text, value

for value in (
    "openssl pkey",
    "openssl rsa",
    "openssl ec",
    "openssl pkcs8",
    "cat \"$key\"",
    "sha256sum \"$key\"",
    "systemctl restart",
    "systemctl reload",
    "systemctl start",
    "systemctl stop",
    "nginx -s",
    "apachectl graceful",
    "certbot",
    "acme.sh",
    "nft add",
    "nft delete",
    "iptables -A",
    "iptables -I",
    "iptables -D",
    "ufw allow",
    "ufw deny",
    "firewall-cmd --add",
    "firewall-cmd --remove",
    "WWCX_MAIL_GATEWAY_TOKEN=",
):
    assert value not in text, value

assert 'http://127.0.0.1:$PORT/healthz' not in text
assert text.count("record message_sent no") == 1
assert text.index("git status --porcelain --untracked-files=all") < text.index("install -d -m 0700")
assert text.index("private_key_contents_read no") > text.index("private-key-path-metadata.txt")
assert text.index("active-edge1-vhosts.txt") < text.index("active_tls_pair_in_enabled_vhost")
assert text.index("validate_client_cidr") < text.index("candidate-parameters.env")

syntax = subprocess.run(["sh", "-n", str(SCRIPT)], cwd=ROOT, check=False)
assert syntax.returncode == 0

runbook = RUNBOOK.read_text(encoding="utf-8")
for value in (
    "edge1.ww.cx",
    "business159",
    "162.0.217.71/32",
    "/outbound-mail/healthz",
    "enabled Apache vhost",
    "/etc/letsencrypt/live/edge1.ww.cx/fullchain.pem",
    "/etc/letsencrypt/live/edge1.ww.cx/privkey.pem",
    "does not read private-key contents",
    "candidate-parameters.env",
    "No live B2 change",
    "proposal-validation audit",
):
    assert value in runbook, value

print("Outbound mail Phase B2 parameter discovery validation passed")
print("The live health route and enabled-vhost TLS references are selected exactly")
print("Certificate inspection is public-metadata only; private-key contents remain unread")
print("One exact measured client CIDR may be supplied for proposal readiness")
