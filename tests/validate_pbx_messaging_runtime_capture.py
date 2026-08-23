#!/usr/bin/env python3
"""Static safety validation for the PBX + Messaging live runtime capture audit."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "communications" / "capture-pbx-messaging-runtime.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "set -euo pipefail",
    "umask 077",
    "EXPECTED_HOST=${EXPECTED_HOST:-edge1.ww.cx}",
    "systemctl",
    "wwcx-messaging-gateway.service",
    "core show channels count",
    "pjsip show endpoints",
    "pjsip show contacts",
    "pjsip show registrations",
    "pjsip show transports",
    "http://127.0.0.1:58080/healthz",
    "http://127.0.0.1:58080/readyz",
    "/var/lib/wwcx-messaging-gateway/private-mms-quarantine",
    "/usr/bin/clamscan",
    "Environment=<redacted>",
    "<redacted>",
    "SHA256SUMS",
)
for marker in required:
    if marker not in text:
        raise SystemExit(f"runtime capture missing required safety marker: {marker}")

prohibited = (
    "systemctl restart",
    "systemctl reload",
    "systemctl stop",
    "systemctl start",
    "systemctl enable",
    "systemctl disable",
    "asterisk -rx 'channel originate",
    "dialplan reload",
    "pjsip send register",
    "rm -rf",
    "chmod 777",
    "nft add",
    "iptables -",
    "ufw allow",
    "curl -X POST",
    "curl --request POST",
    "send_sms",
    "send_mms",
)
for marker in prohibited:
    if marker in text:
        raise SystemExit(f"runtime capture contains prohibited mutation marker: {marker}")

# The private quarantine root may be stat'ed but must never be recursively listed or read.
for marker in ("find \"$QUARANTINE\"", "ls \"$QUARANTINE\"", "cat \"$QUARANTINE", "grep -R"):
    if marker in text:
        raise SystemExit(f"runtime capture may expose private quarantine content: {marker}")

print("PBX + Messaging runtime capture validation passed")
print("Read-only aggregate capture and unit redaction boundaries confirmed")
