#!/usr/bin/env python3
"""Static safety validation for the compact MariaDB/UCP endpoint summary audit."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/security/mariadb_ucp_endpoint_summary_audit.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "Mode: compact read-only summary",
    "ss -Htnpe state established",
    "$3 ~ port_re || $4 ~ port_re",
    "connection_total=",
    "mariadb_connection_pids=",
    "ucp_8001_connection_pids=",
    "ucp_8003_connection_pids=",
    "summarize_listener 3306",
    "summarize_listener 8001",
    "summarize_listener 8003",
    "UCP BIND AND PUBLICATION CONTRACT",
    "endpoint addresses are reduced to scope labels",
    'sub(/^"/, "", token);',
    'sub(/".*$/, "", token);',
    "No database query, grant inspection, service, process, PM2, unit, listener, firewall, WireGuard, configuration, package, client-address, logger, packet capture, external scan, container, or traffic change was performed.",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required summary behavior: {token}")

prohibited_patterns = (
    r"(?m)^\s*(?:sudo\s+)?(?:mysql|mariadb)\b",
    r"(?m)^\s*(?:sudo\s+)?systemctl\s+(?:start|stop|restart|reload|enable|disable|mask|unmask|daemon-reload)\b",
    r"(?m)^\s*(?:sudo\s+)?service\s+\S+\s+(?:start|stop|restart|reload)\b",
    r"(?m)^\s*(?:sudo\s+)?nft\s+(?:add|delete|insert|replace|flush)\b",
    r"(?m)^\s*(?:sudo\s+)?iptables(?:-restore)?(?:\s|$)",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?(?:cp|mv|rm|install|ln|chmod|chown|mkdir)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:pm2|fwconsole)\s+(?:start|stop|restart|reload|delete|save|resurrect)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:strace|gdb|tcpdump|tshark|dumpcap|nmap|masscan|nc|netcat)\b",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited mutation or intrusive command present: {pattern}")

for token in (
    "journalctl",
    "/proc/$pid/environ",
    "process.env",
    "pm2 env",
    "SHOW PROCESSLIST",
    "SELECT ",
    "GRANT ",
):
    if token in text:
        raise SystemExit(f"sensitive or query behavior present: {token}")

if "$4 ~ port_re || $5 ~ port_re" in text:
    raise SystemExit("stale ss endpoint columns detected")
if r'\"' in text:
    raise SystemExit("escaped quote remains in AWK regular expression")

result = subprocess.run(
    ["sh", "-n", str(SCRIPT)],
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
if result.returncode != 0:
    raise SystemExit(f"shell syntax validation failed: {result.stderr.strip()}")

print("MariaDB/UCP endpoint summary audit safety validation passed")
