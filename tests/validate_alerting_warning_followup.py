#!/usr/bin/env python3
"""Static safety validation for the Asterisk warning follow-up audit."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/alerting/asterisk_warning_followup_audit.sh"

text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "pjsip show transports",
    "127.0.0.1:5061",
    "systemctl is-enabled asterisk",
    "http show status",
    "openssl s_client",
    "nft list ruleset",
    "Mode: read-only",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required audit behavior: {token}")

prohibited = (
    "apt-get install",
    "apt-get upgrade",
    "systemctl restart",
    "systemctl start",
    "systemctl stop",
    "systemctl enable",
    "systemctl disable",
    "update-rc.d",
    "nft add",
    "nft delete",
    "nft insert",
    "nft replace",
    "nft flush",
    "sed -i",
    "fwconsole restart",
    "asterisk -rx 'dialplan reload'",
)
for token in prohibited:
    if token in text:
        raise SystemExit(f"prohibited mutation command present: {token}")

print("Asterisk warning follow-up audit safety validation passed")
