#!/usr/bin/env python3
"""Static safety validation for the Asterisk native service preflight audit."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/alerting/asterisk_native_service_preflight_audit.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "Mode: read-only",
    "systemctl show asterisk",
    "systemctl cat asterisk",
    "/etc/init.d/asterisk",
    "/usr/sbin/safe_asterisk",
    "/etc/asterisk/asterisk.conf",
    "systemctl show freepbx",
    "systemctl cat freepbx",
    "list-dependencies --reverse asterisk.service",
    "list-dependencies --reverse freepbx.service",
    "PID_RESOLVED",
    "PID_SOURCE",
    "process_cgroup=",
    "required_native_unit_properties:",
    "no candidate unit is approved solely by this preflight",
    "No service, process, session, cgroup, boot, unit, configuration, listener, firewall, package, call, logger, module, container, or traffic change was performed.",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required preflight behavior: {token}")

prohibited_patterns = (
    r"(?m)^\s*(?:sudo\s+)?apt(?:-get)?\s+(?:install|upgrade|remove|purge)\b",
    r"(?m)^\s*(?:sudo\s+)?systemctl\s+(?:start|stop|restart|reload|enable|disable|mask|unmask|daemon-reload)\b",
    r"(?m)^\s*(?:sudo\s+)?service\s+\S+\s+(?:start|stop|restart|reload)\b",
    r"(?m)^\s*(?:sudo\s+)?nft\s+(?:add|delete|insert|replace|flush)\b",
    r"(?m)^\s*(?:sudo\s+)?iptables(?:-restore)?(?:\s|$)",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?(?:cp|mv|rm|install|ln|chmod|chown|mkdir)\b",
    r"(?m)^\s*(?:sudo\s+)?fwconsole\s+(?:restart|reload|chown|start|stop)\b",
    r"asterisk\s+-rx\s+['\"](?:core reload|dialplan reload|module reload|module unload|logger rotate)",
    r"(?m)^\s*(?:sudo\s+)?(?:strace|gdb|tcpdump|tshark|dumpcap|nmap|masscan|nc|netcat)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:reboot|shutdown|poweroff|halt)\b",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited mutation or intrusive command present: {pattern}")

for token in (
    "journalctl",
    "loginctl terminate",
    "systemd-run",
    "nsenter",
    "cat /etc/asterisk/keys",
    "openssl rsa",
    "openssl pkey",
    "strace -p",
    "gdb -p",
):
    if token in text:
        raise SystemExit(f"sensitive or intrusive behavior present: {token}")

if "valid_asterisk_pid" not in text or "resolve_asterisk_pid" not in text:
    raise SystemExit("guarded Asterisk PID validation is required")

result = subprocess.run(
    ["sh", "-n", str(SCRIPT)],
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
if result.returncode != 0:
    raise SystemExit(f"shell syntax validation failed: {result.stderr.strip()}")

print("Asterisk native service preflight audit safety validation passed")
