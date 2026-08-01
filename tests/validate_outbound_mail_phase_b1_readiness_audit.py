#!/usr/bin/env python3
"""Static safety validation for the read-only Phase B1 readiness audit."""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/messaging/outbound_mail_phase_b1_readiness_audit.sh"
STATE = ROOT / ".agent/outbound-mail-activation.md"
RUNBOOK = ROOT / "docs/messaging-operations/outbound-mail-phase-b1-readiness-audit-20260801.md"
ACCEPTANCE = ROOT / "docs/messaging-operations/outbound-mail-phase-b1-readiness-live-acceptance-20260801.md"

assert SCRIPT.is_file()
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}",
    "PHASE_B_PACKAGE_COMMIT=${PHASE_B_PACKAGE_COMMIT:-c55059c2d0230ea273709bbb5a4169b00bb226c1}",
    "EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1-readiness",
    "output_dir=\"$EVIDENCE_ROOT/$TIMESTAMP\"",
    "--porcelain --untracked-files=all",
    "git -C \"$REPO_ROOT\" merge-base --is-ancestor",
    "protected outbound-mail files changed",
    "config/messaging/outbound-mail-gateway.json",
    "config/messaging/outbound-mail-policy.json",
    "config/messaging/mail-identities.json",
    "committed-safety-error.txt",
    "committed outbound-mail safety validation failed",
    "systemctl is-active --quiet",
    "systemctl is-enabled --quiet",
    "systemctl status \"$SERVICE_NAME\" --no-pager --lines=0 -l",
    "127\\.0\\.0\\.1:8104",
    "port-8104-addresses.txt",
    "grep -Ev '^127\\.0\\.0\\.1:8104$'",
    "port 8104 has a non-approved listener address",
    "/outbound-mail/api/v1/status",
    "/outbound-mail/send",
    "status-validation-error.txt",
    "runtime status safety validation failed",
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
    "EVIDENCE_DIR=",
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

for path in (STATE, RUNBOOK, ACCEPTANCE):
    assert path.is_file(), path
    content = path.read_text(encoding="utf-8")
    assert "c55059c2d0230ea273709bbb5a4169b00bb226c1" in content
    assert "B2" in content
    assert "mail delivery" in content

state_text = STATE.read_text(encoding="utf-8")
assert "production HMAC secret currently installed: **no**" in state_text
assert "temporary activation secret generated during failed attempt: **yes; removed**" in state_text
assert "B1 runtime overlay currently installed: **no**" in state_text
assert "latest Phase B1 attempt outcome: **failed startup race; automatic rollback complete**" in state_text
assert "B1 readiness audit executed and accepted: **yes**" in state_text
assert "B1 readiness state: **ready for explicit B1 authorization**" in state_text
assert "2026-08-01T17:45:48Z" in state_text
assert "bf7c9186f416d69e20f289a68c7a45314baae6b8" in state_text
assert "/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1-readiness/20260801T174548Z" in state_text

runbook_text = RUNBOOK.read_text(encoding="utf-8")
assert "No production secret exists" in runbook_text
assert "sudo sh tools/messaging/outbound_mail_phase_b1_readiness_audit.sh" in runbook_text
assert "Authorize generation of a new production HMAC secret" in runbook_text
assert "Do not install B2" in runbook_text

acceptance_text = ACCEPTANCE.read_text(encoding="utf-8")
for value in (
    "Host: `edge1.ww.cx`",
    "authenticated SSH as `wwadmin`",
    "Audit principal: `root` through `sudo`",
    "2026-08-01T17:45:48Z",
    "readiness_state=ready_for_explicit_b1_authorization",
    "head_commit=bf7c9186f416d69e20f289a68c7a45314baae6b8",
    "unsigned preparation API request remained denied with HTTP `403`",
    "send probe remained denied with HTTP `403`",
    "secret_generated=no",
    "secret_read=no",
    "runtime_files_modified=no",
    "service_restarted=no",
    "proxy_modified=no",
    "dns_modified=no",
    "firewall_modified=no",
    "message_sent=no",
    "/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1-readiness/20260801T174548Z",
    "production HMAC secret: not generated or installed",
    "Authorize generation of a new production HMAC secret",
):
    assert value in acceptance_text, value

print("Outbound mail Phase B1 read-only readiness audit validation passed")
print("Live readiness acceptance remains valid after the rolled-back activation attempt")
print("No B1 credential or runtime overlay is currently installed")
