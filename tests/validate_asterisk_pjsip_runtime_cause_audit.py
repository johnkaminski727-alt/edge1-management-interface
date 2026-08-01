#!/usr/bin/env python3
"""Static safety validation for the PJSIP runtime-cause audit."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/alerting/asterisk_pjsip_runtime_cause_audit.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "Mode: read-only",
    "pjsip show transports",
    "pjsip show transport 0.0.0.0-udp",
    "journalctl -u asterisk",
    "/var/log/asterisk/full",
    "sanitize_stream",
    "sip:[redacted]",
    "PJSIP/[redacted]",
    "sha256sum",
    "No configuration, service, listener, route, certificate, firewall, package, call, or logger change was performed.",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required audit behavior: {token}")

prohibited_patterns = (
    r"(?m)^\s*(?:sudo\s+)?apt(?:-get)?\s+(?:install|upgrade|remove|purge)\b",
    r"(?m)^\s*(?:sudo\s+)?systemctl\s+(?:start|stop|restart|reload|enable|disable|mask|unmask)\b",
    r"(?m)^\s*(?:sudo\s+)?service\s+\S+\s+(?:start|stop|restart|reload)\b",
    r"(?m)^\s*(?:sudo\s+)?update-rc\.d\b",
    r"(?m)^\s*(?:sudo\s+)?nft\s+(?:add|delete|insert|replace|flush)\b",
    r"(?m)^\s*(?:sudo\s+)?iptables(?:-restore)?(?:\s|$)",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?(?:cp|mv|rm|install)\b",
    r"(?m)^\s*(?:sudo\s+)?fwconsole\s+(?:restart|reload)\b",
    r"asterisk\s+-rx\s+['\"](?:core reload|dialplan reload|module reload|logger rotate)",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited mutation command present: {pattern}")

sensitive_patterns = (
    'cat /etc/asterisk/keys',
    'openssl rsa',
    'openssl pkey',
    'grep -R /etc/asterisk/keys',
)
for token in sensitive_patterns:
    if token in text:
        raise SystemExit(f"sensitive material inspection present: {token}")

if "tail -n 30000" not in text or "tail -n 300" not in text:
    raise SystemExit("Asterisk log inspection must be bounded")

print("Asterisk PJSIP runtime-cause audit safety validation passed")
