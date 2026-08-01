#!/usr/bin/env python3
"""Static safety validation for the authorized Phase B1 activation wrapper."""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/messaging/activate-outbound-mail-phase-b1.sh"
INSTALLER = ROOT / "deploy/messaging/install-outbound-mail-preparation-api.sh"
STATE = ROOT / ".agent/outbound-mail-activation.md"

assert SCRIPT.is_file()
assert INSTALLER.is_file()
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}",
    "EXPECTED_COMMIT=${EXPECTED_COMMIT:-}",
    "APPROVED_ACTIVATION_COMMIT=${APPROVED_ACTIVATION_COMMIT:-}",
    "APPROVED_ACTIVATION_COMMIT is required",
    "APPROVED_ACTIVATION_COMMIT must be a full lowercase commit SHA",
    "PHASE_B_PACKAGE_COMMIT=${PHASE_B_PACKAGE_COMMIT:-c55059c2d0230ea273709bbb5a4169b00bb226c1}",
    "READINESS_EVIDENCE=${READINESS_EVIDENCE:-/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1-readiness/20260801T174548Z}",
    "INSTALLER_SUCCEEDED=false",
    "ACTIVATION_ACCEPTED=false",
    "status --porcelain --untracked-files=all",
    "merge-base --is-ancestor",
    "cat-file -e \"${APPROVED_ACTIVATION_COMMIT}^{commit}\"",
    "approved activation commit is not present in the repository",
    "approved activation commit is not an ancestor of HEAD",
    "deploy/messaging/activate-outbound-mail-phase-b1.sh",
    "diff --quiet \"$APPROVED_ACTIVATION_COMMIT\"..HEAD",
    "protected Phase B files changed after the approved activation baseline",
    "sha256sum -c SHA256SUMS",
    "readiness_state=ready_for_explicit_b1_authorization",
    "secret_generated=no",
    "runtime_files_modified=no",
    "service_restarted=no",
    "proxy_modified=no",
    "dns_modified=no",
    "firewall_modified=no",
    "message_sent=no",
    "B1 runtime material already exists",
    "127.0.0.1:8104",
    "unsigned preparation status must remain HTTP 403",
    "send endpoint must remain HTTP 403",
    "outbound-mail/api/v1",
    "findmnt -n -o FSTYPE /run",
    "mktemp /run/wwcx-outbound-mail-b1-secret.XXXXXX",
    "secrets.token_urlsafe(48)",
    "chmod 0600",
    "SECRET_SOURCE_FILE=\"$SECRET_SOURCE\"",
    "ACTION=install",
    "INSTALLER_SUCCEEDED=true",
    "rollback_if_needed",
    "ACTION=disable",
    "restoring the Phase A disabled state",
    "ACTIVATION_ACCEPTED=true",
    "rm -f -- \"$SECRET_SOURCE\"",
    "runtime environment file mode is not 0600",
    'status["preparation_api"]["enabled"] is True',
    'status["preparation_api"]["runtime_secret_configured"] is True',
    'status["external_delivery_enabled"] is False',
    'status["policy_enabled"] is False',
    'status["sender_selection"]["live_sender_count"] == 0',
    "B2 reverse proxy: not installed",
    "External delivery: disabled",
)
for value in required:
    assert value in text, value

prohibited = (
    "echo $SECRET",
    "echo \"$SECRET",
    "printf '%s' \"$SECRET",
    "sha256sum \"$SECRET_SOURCE\"",
    "base64 \"$SECRET_SOURCE\"",
    "cat \"$SECRET_SOURCE\"",
    "openssl rand",
    "certbot",
    "nginx -s reload",
    "apachectl graceful",
    "iptables ",
    "nft ",
    "ufw ",
    "firewall-cmd",
    "systemctl enable nginx",
    "allow_live_delivery",
    "smtp_cutover_authorized",
    "APPROVED_ACTIVATION_COMMIT=${APPROVED_ACTIVATION_COMMIT:-79d6591e8f7ae8b404bff9cb3a4ab8929a63817c}",
)
for value in prohibited:
    assert value not in text, value

assert "trap on_exit EXIT" in text
assert "trap on_signal HUP INT TERM" in text
assert "trap - EXIT HUP INT TERM" in text
assert "exit 130" in text
assert text.count('rm -f -- "$SECRET_SOURCE"') >= 2
assert 'The production secret will not be displayed, hashed, or copied into deployment evidence.' in text
assert text.index("APPROVED_ACTIVATION_COMMIT is required") < text.index("mktemp /run/wwcx-outbound-mail-b1-secret")
assert text.index("protected Phase B files changed after the approved activation baseline") < text.index("mktemp /run/wwcx-outbound-mail-b1-secret")
assert text.index("INSTALLER_SUCCEEDED=true") < text.index("ACTIVATION_ACCEPTED=true")

syntax = subprocess.run(["sh", "-n", str(SCRIPT)], cwd=ROOT, check=False)
assert syntax.returncode == 0

installer = INSTALLER.read_text(encoding="utf-8")
assert "wait_for_gateway()" in installer
assert "health-after-restart.json" in installer
assert "readiness-after-restart.txt" in installer
assert installer.index("health-after-restart.json") < installer.index('python3 "$CANARY"')

state = STATE.read_text(encoding="utf-8")
assert "Phase B1 activation authorized: **yes**" in state
assert "Phase B1 activation attempts: **1**" in state
assert "latest Phase B1 attempt outcome: **failed startup race; automatic rollback complete**" in state
assert "Phase B1 activation completed successfully: **no**" in state
assert "temporary activation secret generated during failed attempt: **yes; removed**" in state
assert "production HMAC secret currently installed: **no**" in state
assert "approved activation baseline commit must be supplied explicitly" in state
assert "B2 certificate or reverse proxy installed: **no**" in state
assert "production mail delivery: **no**" in state
assert "2026-08-01 18:38 UTC" in state
assert "/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1/20260801T183528Z" in state

print("Authorized outbound mail Phase B1 activation wrapper validation passed")
print("An explicit approved activation baseline is required before secret generation")
print("Secret generation is temporary, non-disclosing, loopback-only, and rollback-backed")
print("Failed startup race and clean Phase A rollback are recorded")
print("Startup readiness wait precedes the signed canary")
print("B2, DNS, firewall, provider, sender, and delivery activation remain absent")
