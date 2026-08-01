#!/usr/bin/env python3
"""Static safety validation for the Asterisk service lifecycle audit."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/alerting/asterisk_service_lifecycle_audit.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "Mode: read-only",
    "systemctl show asterisk",
    "-p MainPID",
    "-p ControlGroup",
    "systemctl status asterisk --no-pager --lines=0",
    "systemctl cat asterisk",
    "/proc/$PID/cgroup",
    "parent_chain:",
    "loginctl show-session",
    "loginctl show-user",
    "/etc/systemd/logind.conf",
    "systemctl list-unit-files 'asterisk.service'",
    "sha256sum /etc/init.d/asterisk",
    "/etc/rc0.d",
    "PID_RESOLVED=$candidate",
    'PID_SOURCE="pidfile:$pidfile"',
    "The Asterisk process is attached to a user-session cgroup",
    "No service, process, session, cgroup, boot, configuration, listener, firewall, package, call, logger, module, container, or traffic change was performed.",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required lifecycle-audit behavior: {token}")

prohibited_patterns = (
    r"(?m)^\s*(?:sudo\s+)?apt(?:-get)?\s+(?:install|upgrade|remove|purge)\b",
    r"(?m)^\s*(?:sudo\s+)?systemctl\s+(?:start|stop|restart|reload|enable|disable|mask|unmask|kill|reset-failed)\b",
    r"(?m)^\s*(?:sudo\s+)?service\s+\S+\s+(?:start|stop|restart|reload)\b",
    r"(?m)^\s*(?:sudo\s+)?loginctl\s+(?:terminate|kill|enable-linger|disable-linger|lock-session|unlock-session)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:kill|pkill|killall)\b",
    r"(?m)^\s*(?:sudo\s+)?nft\s+(?:add|delete|insert|replace|flush)\b",
    r"(?m)^\s*(?:sudo\s+)?iptables(?:-restore)?(?:\s|$)",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?(?:cp|mv|rm|install|ln|chmod|chown)\b",
    r"(?m)^\s*(?:sudo\s+)?fwconsole\s+(?:restart|reload)\b",
    r"asterisk\s+-rx\s+['\"](?:core reload|dialplan reload|module reload|module unload|logger rotate)",
    r"(?m)^\s*(?:sudo\s+)?(?:strace|gdb|tcpdump|tshark|dumpcap|nmap|masscan|nc|netcat)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:tee|truncate)\s+/sys/fs/cgroup/",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited mutation or intrusive command present: {pattern}")

for token in (
    "journalctl",
    "RemoteHost",
    "systemctl status asterisk --no-pager --lines=30",
    "cat /etc/asterisk/keys",
    "strace -p",
    "gdb -p",
):
    if token in text:
        raise SystemExit(f"sensitive, verbose, or intrusive behavior present: {token}")

if "valid_asterisk_pid" not in text or "resolve_asterisk_pid" not in text:
    raise SystemExit("guarded Asterisk PID validation is required")

print("Asterisk service lifecycle audit safety validation passed")
