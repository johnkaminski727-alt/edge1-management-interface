#!/usr/bin/env python3
"""Static safety validation for the comprehensive Edge1 listener audit."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/security/edge1_comprehensive_listener_exposure_audit.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "Mode: read-only",
    "local observation only",
    "not an external Internet scan",
    "ss -H -lntup",
    "systemctl list-sockets",
    "systemctl list-unit-files",
    "http show status",
    "manager show settings",
    "ari show status",
    "rtp show settings",
    "pjsip show transports",
    "ASTERISK_HIGH_UDP",
    "apache2ctl -S",
    "docker ps --format",
    "podman ps --format",
    "nft -a list chain inet wwcxfw input",
    "No configuration, service, listener, route, certificate, firewall, package, call, container, or traffic change was performed.",
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
    r"(?m)^\s*(?:sudo\s+)?(?:ufw|firewall-cmd)\s+(?:allow|deny|reject|enable|disable|reload)\b",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?(?:cp|mv|rm|install|chmod|chown)\b",
    r"(?m)^\s*(?:sudo\s+)?fwconsole\s+(?:restart|reload|setting|ma)\b",
    r"asterisk\s+-rx\s+['\"](?:core reload|dialplan reload|module reload|logger rotate)",
    r"(?m)^\s*(?:sudo\s+)?docker\s+(?:run|start|stop|restart|rm|kill|pause|unpause|update|network|compose)\b",
    r"(?m)^\s*(?:sudo\s+)?podman\s+(?:run|start|stop|restart|rm|kill|pause|unpause|network)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:nmap|masscan|nc|netcat)\b",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited mutation or active-scan command present: {pattern}")

sensitive_patterns = (
    "cat /etc/asterisk/keys",
    "openssl rsa",
    "openssl pkey",
    "nginx -T",
    "docker inspect",
    "podman inspect",
    "/proc/*/environ",
)
for token in sensitive_patterns:
    if token in text:
        raise SystemExit(f"sensitive inspection present: {token}")

print("Edge1 comprehensive listener exposure audit safety validation passed")
