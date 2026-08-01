#!/usr/bin/env python3
"""Static safety checks for the Asterisk transport and exposure audit."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/alerting/asterisk_transport_exposure_audit.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "Mode: read-only",
    "pjsip show transports",
    "pjsip show endpoints",
    "127.0.0.1:5061",
    "http show status",
    "openssl x509",
    "openssl s_client",
    "nft -a list ruleset",
    "systemctl is-enabled asterisk",
    "No configuration, listener, certificate, firewall, route, service, or package change was performed.",
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
    r"(?m)^\s*(?:sudo\s+)?(?:ip6?tables-restore|iptables-restore)\b",
    r"(?m)^\s*(?:sudo\s+)?ip6?tables(?:-legacy)?\s+(?:-A|-D|-I|-R|-F|-X|-P|--append|--delete|--insert|--replace|--flush|--new-chain|--delete-chain|--policy)\b",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?cp\b",
    r"(?m)^\s*(?:sudo\s+)?mv\b",
    r"(?m)^\s*(?:sudo\s+)?rm\b",
    r"(?m)^\s*(?:sudo\s+)?install\b",
    r"(?m)^\s*(?:sudo\s+)?fwconsole\s+(?:restart|reload)\b",
    r"asterisk\s+-rx\s+['\"](?:core reload|dialplan reload|module reload)",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited mutation command present: {pattern}")

if "tlsprivatekey" not in text:
    raise SystemExit("audit must identify the configured key path for metadata review")
if "cat \"$CERT_PATH\"" in text or "openssl rsa" in text or "openssl pkey" in text:
    raise SystemExit("audit must not expose private-key material")

print("Asterisk transport and exposure audit safety validation passed")
