#!/usr/bin/env python3
"""Static safety validation for the Asterisk FD origin probe."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/alerting/asterisk_fd_origin_probe.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "Mode: read-only",
    "core show help core show fd",
    "core show fd",
    "core show threads",
    "/proc/$PID/fdinfo/$fd",
    "module show like res_resolver_unbound",
    "module show like res_rtp_asterisk",
    "module show like res_stun_monitor",
    "pidfile:/run/asterisk/asterisk.pid",
    "process-table:unique-asterisk-f",
    "No tracer, packet capture, configuration, service, listener, route, certificate, firewall, package, call, logger, module, container, or traffic change was performed.",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required probe behavior: {token}")

prohibited_patterns = (
    r"(?m)^\s*(?:sudo\s+)?apt(?:-get)?\s+(?:install|upgrade|remove|purge)\b",
    r"(?m)^\s*(?:sudo\s+)?systemctl\s+(?:start|stop|restart|reload|enable|disable|mask|unmask)\b",
    r"(?m)^\s*(?:sudo\s+)?service\s+\S+\s+(?:start|stop|restart|reload)\b",
    r"(?m)^\s*(?:sudo\s+)?nft\s+(?:add|delete|insert|replace|flush)\b",
    r"(?m)^\s*(?:sudo\s+)?iptables(?:-restore)?(?:\s|$)",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?(?:cp|mv|rm|install)\b",
    r"(?m)^\s*(?:sudo\s+)?fwconsole\s+(?:restart|reload)\b",
    r"asterisk\s+-rx\s+['\"](?:core reload|dialplan reload|module reload|module unload|logger rotate)",
    r"(?m)^\s*(?:sudo\s+)?(?:strace|gdb|tcpdump|tshark|dumpcap|nmap|masscan|nc|netcat)\b",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited mutation or intrusive command present: {pattern}")

for token in (
    "cat /etc/asterisk/keys",
    "openssl rsa",
    "openssl pkey",
    "grep -R /etc/asterisk/keys",
    "strace -p",
    "gdb -p",
):
    if token in text:
        raise SystemExit(f"sensitive or intrusive behavior present: {token}")

if "valid_asterisk_pid" not in text or "resolve_asterisk_pid" not in text:
    raise SystemExit("guarded Asterisk PID validation is required")

print("Asterisk FD origin probe safety validation passed")
