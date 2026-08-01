#!/usr/bin/env python3
"""Static safety validation for the read-only Phase B1 readiness audit."""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/messaging/outbound_mail_phase_b1_readiness_audit.sh"
STATE = ROOT / ".agent/outbound-mail-activation.md"
RUNBOOK = ROOT / "docs/messaging-operations/outbound-mail-phase-b1-readiness-audit-20260801.md"

assert SCRIPT.is_file()
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}",
    "PHASE_B_PACKAGE_COMMIT=${PHASE_B_PACKAGE_COMMIT:-c55059c2d0230ea273709bbb5a4169b00bb226c1}",
    "git -C \"$REPO_ROOT\" merge-base --is-ancestor",
    "protected outbound-mail files changed",
    "config/messaging/outbound-mail-gateway.json",
    "config/messaging/outbound-mail-policy.json",
    "config/messaging/mail-identities.json",
    "systemctl is-active --quiet",
    "systemctl is-enabled --quiet",
    "127\\.0\\.0\\.1:8104",
    "/outbound-mail/api/v1/status",
    "/outbound-mail/send",
    "runtime_secret_configured",
    "/etc/wwcx/outbound-mail-gateway.env",
    "runtime-file-metadata.tsv",
    "proxy-path-matches.txt",
    "secret_generated no",
    "secret_read no",
    "runtime_files_modified no",
    "service_restarted no",
    "proxy_modified no",
    "dns_modified no",
    "firewall_modified no",
    "message_sent no",
    "ready_for_explicit_b1_authorization",
    "SHA256SUMS",
)
for value in required:
    assert value in text, value

for prohibited in (
    "systemctl restart",
    "systemctl start",
    "systemctl stop",
    "systemctl daemon-reload",
    "nginx -s reload",
    "apachectl graceful",
    "service nginx reload",
    "service apache2 reload",
    "iptables ",
    "nft ",
    "ufw ",
    "firewall-cmd",
    "certbot",
    "openssl rand",
    "uuidgen",
    "secrets.token",
    "WWCX_MAIL_GATEWAY_TOKEN=",
    "cat /etc/wwcx/outbound-mail-gateway.env",
    "source /etc/wwcx/outbound-mail-gateway.env",
    ". /etc/wwcx/outbound-mail-gateway.env",
    "rm -f /etc/",
    "cp ",
    "mv ",
    "sed -i",
):
    assert prohibited not in text, prohibited

syntax = subprocess.run(["sh", "-n", str(SCRIPT)], cwd=ROOT, check=False)
assert syntax.returncode == 0

for path in (STATE, RUNBOOK):
    assert path.is_file(), path
    content = path.read_text(encoding="utf-8")
    assert "c55059c2d0230ea273709bbb5a4169b00bb226c1" in content
    assert "20260801T064714Z" in content
    assert "no production secret" in content.lower()
    assert "B2" in content
    assert "mail delivery" in content

state_text = STATE.read_text(encoding="utf-8")
assert "ready for explicit B1 authorization" in state_text
assert "not executed in this session" in state_text

runbook_text = RUNBOOK.read_text(encoding="utf-8")
assert "sudo sh tools/messaging/outbound_mail_phase_b1_readiness_audit.sh" in runbook_text
assert "Authorize generation of a new production HMAC secret" in runbook_text
assert "Do not install B2" in runbook_text

print("Outbound mail Phase B1 read-only readiness audit validation passed")
print("No secret generation, service restart, proxy, DNS, firewall, or delivery mutation is present")
