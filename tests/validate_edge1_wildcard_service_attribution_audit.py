#!/usr/bin/env python3
"""Static safety validation for Edge1 wildcard service attribution."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/security/edge1_wildcard_service_attribution_audit.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "Mode: read-only",
    "MariaDB TCP 3306",
    "Node TCP 8001/8003",
    "systemctl show mariadb.service",
    "systemctl show mariadb.socket",
    "listener_pids",
    "grep -oE 'pid=[0-9]+'",
    "mariadb_listener_pids=",
    "node_script=",
    "established_tcp_3306_count=",
    "established_tcp_8001_count=",
    "established_tcp_8003_count=",
    "MARIADB BINDING CONFIGURATION",
    "LOCAL PROXY AND UNIT REFERENCES",
    "nft -a list chain inet wwcxfw input",
    "No database, service, process, unit, listener, firewall, configuration, package, logger, container, or traffic change was performed.",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required attribution behavior: {token}")

prohibited_patterns = (
    r"(?m)^\s*(?:sudo\s+)?apt(?:-get)?\s+(?:install|upgrade|remove|purge)\b",
    r"(?m)^\s*(?:sudo\s+)?systemctl\s+(?:start|stop|restart|reload|enable|disable|mask|unmask|daemon-reload)\b",
    r"(?m)^\s*(?:sudo\s+)?service\s+\S+\s+(?:start|stop|restart|reload)\b",
    r"(?m)^\s*(?:sudo\s+)?nft\s+(?:add|delete|insert|replace|flush)\b",
    r"(?m)^\s*(?:sudo\s+)?iptables(?:-restore)?(?:\s|$)",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?(?:cp|mv|rm|install|ln|chmod|chown|mkdir)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:mysql|mariadb|mysqladmin|mariadb-admin)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:strace|gdb|tcpdump|tshark|dumpcap|nmap|masscan|nc|netcat)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:reboot|shutdown|poweroff|halt)\b",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited mutation or intrusive command present: {pattern}")

for token in (
    "/proc/$pid/environ",
    "/proc/$pid/mem",
    "journalctl",
    "SHOW GRANTS",
    "SELECT ",
    "mysql.user",
    "--password",
    "MYSQL_PWD",
    "strace -p",
    "gdb -p",
):
    if token in text:
        raise SystemExit(f"sensitive or intrusive behavior present: {token}")

if "systemctl cat \"$unit\"" in text or "cat /proc/$pid/cmdline" in text:
    raise SystemExit("unfiltered unit or command-line disclosure is prohibited")

result = subprocess.run(
    ["sh", "-n", str(SCRIPT)],
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
if result.returncode != 0:
    raise SystemExit(f"shell syntax validation failed: {result.stderr.strip()}")

print("Edge1 wildcard service attribution audit safety validation passed")
