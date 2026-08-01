#!/usr/bin/env python3
"""Static safety validation for the Asterisk warning follow-up audit."""
import re
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

prohibited_patterns = (
    r"\bapt-get[ \t]+(install|upgrade|dist-upgrade|full-upgrade)\b",
    r"\bsystemctl[ \t]+(start|stop|restart|enable|disable|mask|unmask)\b",
    r"\bservice[ \t]+\S+[ \t]+(start|stop|restart)\b",
    r"\bupdate-rc\.d\b",
    r"\bnft[ \t]+(add|delete|insert|replace|flush)\b",
    r"\bsed[ \t]+-i\b",
    r"\bfwconsole[ \t]+restart\b",
    r"asterisk[ \t]+-rx[ \t]+['\"]dialplan reload['\"]",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited mutation command present: {pattern}")

print("Asterisk warning follow-up audit safety validation passed")
