#!/usr/bin/env python3
"""Static safety validation for the Asterisk transport policy follow-up audit."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/alerting/asterisk_transport_policy_followup_audit.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "Mode: read-only",
    "#(try)?include",
    "pjsip show transports",
    "pjsip show transport 0.0.0.0-udp",
    "pjsip show settings",
    "SORCERY AND REALTIME MAPPINGS",
    "127.0.0.1:5061",
    "FOCUSED CONSUMER REFERENCES",
    "FIREWALL INPUT POLICY PATHS",
    "nft -a list chain",
    "No configuration, service, listener, route, certificate, firewall, package, or call change was performed.",
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
    r"(?m)^\s*(?:sudo\s+)?iptables(?:\s|$)",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?(?:cp|mv|rm|install)\b",
    r"(?m)^\s*(?:sudo\s+)?fwconsole\s+(?:restart|reload)\b",
    r"asterisk\s+-rx\s+['\"](?:core reload|dialplan reload|module reload)",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited mutation command present: {pattern}")

for excluded in ("--exclude-dir=.git", "--exclude-dir='venv*'", "--exclude-dir='.venv*'"):
    if excluded not in text:
        raise SystemExit(f"consumer search must exclude noisy runtime trees: {excluded}")

print("Asterisk transport policy follow-up audit safety validation passed")
