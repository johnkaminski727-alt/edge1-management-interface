#!/usr/bin/env python3
"""Static safety validation for the Asterisk high UDP attribution audit."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/alerting/asterisk_high_udp_socket_attribution_audit.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "Mode: read-only",
    "valid_asterisk_pid",
    "systemctl show -p MainPID --value asterisk",
    "/run/asterisk/asterisk.pid",
    "/var/run/asterisk/asterisk.pid",
    "process_table",
    "pid_source=",
    "/proc/$candidate/comm",
    "ss -H -lunpe",
    "/proc/net/udp",
    "/proc/net/udp6",
    "rtp show settings",
    "net.ipv4.ip_local_port_range",
    "module show like res_stun_monitor",
    "module show like res_resolver",
    "No tracer, packet capture, configuration, service, listener, route, certificate, firewall, package, call, logger, container, or traffic change was performed.",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required audit behavior: {token}")

prohibited_patterns = (
    r"(?m)^\s*(?:sudo\s+)?apt(?:-get)?\s+(?:install|upgrade|remove|purge)\b",
    r"(?m)^\s*(?:sudo\s+)?systemctl\s+(?:start|stop|restart|reload|enable|disable|mask|unmask)\b",
    r"(?m)^\s*(?:sudo\s+)?service\s+\S+\s+(?:start|stop|restart|reload)\b",
    r"(?m)^\s*(?:sudo\s+)?nft\s+(?:add|delete|insert|replace|flush)\b",
    r"(?m)^\s*(?:sudo\s+)?iptables(?:-restore)?(?:\s|$)",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?(?:cp|mv|rm|install|kill|pkill|killall)\b",
    r"(?m)^\s*(?:sudo\s+)?fwconsole\s+(?:restart|reload)\b",
    r"asterisk\s+-rx\s+['\"](?:core reload|dialplan reload|module reload|logger rotate)",
    r"(?m)^\s*(?:sudo\s+)?(?:strace|gdb|tcpdump|tshark|dumpcap|nmap|masscan|nc|netcat)\b",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited mutation or intrusive command present: {pattern}")

sensitive_patterns = (
    "cat /etc/asterisk/keys",
    "openssl rsa",
    "openssl pkey",
    "grep -R /etc/asterisk/keys",
    "tcpdump",
    "strace -p",
    "gdb -p",
)
for token in sensitive_patterns:
    if token in text:
        raise SystemExit(f"sensitive or intrusive behavior present: {token}")

if "safe_config_lines" not in text or "sha256sum" not in text:
    raise SystemExit("sanitized configuration metadata and hashes are required")

if text.index("systemctl show -p MainPID") > text.index("/run/asterisk/asterisk.pid"):
    raise SystemExit("systemd MainPID must remain the first PID source")
if text.index("/run/asterisk/asterisk.pid") > text.index("process_table"):
    raise SystemExit("PID files must be checked before the process-table fallback")

print("Asterisk high UDP socket attribution audit safety validation passed")
