#!/usr/bin/env python3
"""Static safety validation for the FreePBX/Asterisk orchestration audit."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/alerting/freepbx_asterisk_orchestration_audit.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "Mode: read-only",
    "systemctl show asterisk.service",
    "systemctl show freepbx.service",
    "systemctl cat asterisk.service",
    "systemctl cat freepbx.service",
    "fwconsole_path=",
    "FREEPBX ORCHESTRATION SOURCE REFERENCES",
    "/etc/init.d/asterisk",
    "/usr/sbin/safe_asterisk",
    "freepbx_control_group=",
    "freepbx_declares_asterisk_relationship=",
    "native_service_design_gates:",
    "choose one long-running supervisor: systemd or safe_asterisk, not both",
    "No service, process, PM2, session, cgroup, boot, unit, configuration, listener, firewall, package, call, database, logger, module, container, or traffic change was performed.",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required orchestration behavior: {token}")

prohibited_patterns = (
    r"(?m)^\s*(?:sudo\s+)?apt(?:-get)?\s+(?:install|upgrade|remove|purge)\b",
    r"(?m)^\s*(?:sudo\s+)?systemctl\s+(?:start|stop|restart|reload|enable|disable|mask|unmask|daemon-reload)\b",
    r"(?m)^\s*(?:sudo\s+)?service\s+\S+\s+(?:start|stop|restart|reload)\b",
    r"(?m)^\s*(?:sudo\s+)?fwconsole\s+(?:start|stop|restart|reload|chown)\b",
    r"(?m)^\s*(?:sudo\s+)?pm2\s+(?:start|stop|restart|reload|delete|save|startup)\b",
    r"(?m)^\s*(?:sudo\s+)?nft\s+(?:add|delete|insert|replace|flush)\b",
    r"(?m)^\s*(?:sudo\s+)?iptables(?:-restore)?(?:\s|$)",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?(?:cp|mv|rm|install|ln|chmod|chown|mkdir)\b",
    r"asterisk\s+-rx\s+['\"](?:core reload|dialplan reload|module reload|module unload|logger rotate)",
    r"(?m)^\s*(?:sudo\s+)?(?:strace|gdb|tcpdump|tshark|dumpcap|nmap|masscan|nc|netcat)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:reboot|shutdown|poweroff|halt)\b",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited mutation or intrusive command present: {pattern}")

for token in (
    "journalctl",
    "/proc/$pid/environ",
    "pm2 jlist",
    "pm2 env",
    "loginctl terminate",
    "systemd-run",
    "nsenter",
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

print("FreePBX Asterisk orchestration audit safety validation passed")
