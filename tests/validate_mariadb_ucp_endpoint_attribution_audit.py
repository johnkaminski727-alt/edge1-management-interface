#!/usr/bin/env python3
"""Static safety validation for the corrected MariaDB/UCP endpoint audit."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/security/mariadb_ucp_endpoint_attribution_audit.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "Mode: read-only",
    "endpoint addresses are reduced to scope labels",
    "ss -Htnpe state established",
    "$3 ~ port_re || $4 ~ port_re",
    "local_service_endpoint",
    "local_client_to_service",
    "connection_pids",
    "process_cgroup=",
    "MARIADB LISTENER AND TRANSPORT CONTRACT",
    "UCP BIND POLICY SOURCE",
    "UCP CLIENT PUBLICATION REFERENCES",
    "serverS?\\.listen",
    "No database query, grant inspection, service, process, PM2, unit, listener, firewall, WireGuard, configuration, package, client-address, logger, packet capture, external scan, container, or traffic change was performed.",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required endpoint-attribution behavior: {token}")

# The corrected field contract for `ss ... state established` is local=$3, peer=$4.
for bad in (
    'scope($4) "__peer_" scope($5)',
    '$4 ~ /:3306$/ {',
    '$4 ~ /:(8001|8003)$/ {',
):
    if bad in text:
        raise SystemExit(f"stale ss field-index logic present: {bad}")

prohibited_patterns = (
    r"(?m)^\s*(?:sudo\s+)?(?:mysql|mariadb|mysqladmin|mysqldump)\b",
    r"(?m)^\s*(?:sudo\s+)?systemctl\s+(?:start|stop|restart|reload|enable|disable|mask|unmask|daemon-reload)\b",
    r"(?m)^\s*(?:sudo\s+)?service\s+\S+\s+(?:start|stop|restart|reload)\b",
    r"(?m)^\s*(?:sudo\s+)?pm2\s+(?:start|stop|restart|reload|delete|save|resurrect)\b",
    r"(?m)^\s*(?:sudo\s+)?nft\s+(?:add|delete|insert|replace|flush)\b",
    r"(?m)^\s*(?:sudo\s+)?iptables(?:-restore)?(?:\s|$)",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?(?:cp|mv|rm|install|ln|chmod|chown|mkdir)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:strace|gdb|tcpdump|tshark|dumpcap|nmap|masscan|nc|netcat)\b",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited mutation or intrusive command present: {pattern}")

for token in (
    "/proc/$pid/environ",
    "pm2 env",
    "journalctl",
    "SHOW PROCESSLIST",
    "information_schema",
    "performance_schema",
    "mysql.user",
):
    if token in text:
        raise SystemExit(f"sensitive or query behavior present: {token}")

result = subprocess.run(
    ["sh", "-n", str(SCRIPT)],
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
if result.returncode != 0:
    raise SystemExit(f"shell syntax validation failed: {result.stderr.strip()}")

print("MariaDB/UCP endpoint attribution audit safety validation passed")
