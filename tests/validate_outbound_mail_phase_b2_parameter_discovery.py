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
    "outbound-mail-phase-b2-parameter-discovery",
    "install -d -m 0700",
    "git status --porcelain --untracked-files=all",
    "127.0.0.1:$PORT",
    "unsigned_api_status_http",
    "send_probe_http",
    "proxy-certificate-references.txt",
    "certificate-candidates.txt",
    "private-key-path-metadata.txt",
    "contents_read=no",
    "candidate-parameters.env",
    "BUSINESS159_EGRESS_MEASUREMENT_REQUIRED",
    "awaiting_business159_egress_measurement",
    "awaiting_certificate_selection_and_business159_egress_measurement",
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

assert text.count("record message_sent no") == 1
assert text.index("git status --porcelain --untracked-files=all") < text.index("install -d -m 0700")
assert text.index("private_key_contents_read no") > text.index("private-key-path-metadata.txt")

syntax = subprocess.run(["sh", "-n", str(SCRIPT)], cwd=ROOT, check=False)
assert syntax.returncode == 0

runbook = RUNBOOK.read_text(encoding="utf-8")
for value in (
    "edge1.ww.cx",
    "business159",
    "actual outbound NAT address",
    "does not read private-key contents",
    "candidate-parameters.env",
    "No live B2 change",
    "proposal-validation audit",
):
    assert value in runbook, value

print("Outbound mail Phase B2 parameter discovery validation passed")
print("Certificate inspection is public-metadata only; private-key contents remain unread")
print("Client CIDR remains dependent on measured business159 egress")
