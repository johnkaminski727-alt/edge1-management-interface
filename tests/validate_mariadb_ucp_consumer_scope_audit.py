#!/usr/bin/env python3
"""Static safety validation for the MariaDB/UCP consumer scope audit."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/security/mariadb_ucp_consumer_scope_audit.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "Mode: read-only",
    "no database query",
    "systemctl show mariadb.socket",
    "systemctl cat mariadb.socket",
    "MARIADB ESTABLISHED CONNECTION SCOPE COUNTS",
    "tcp_3306_established_total=",
    "DATABASE TRANSPORT CANDIDATES",
    "db_transport_scopes=",
    "UCP LISTENER PROCESS",
    "UCP BIND AND CONSUMER SOURCE REFERENCES",
    "tcp_8001_established_total=",
    "tcp_8003_established_total=",
    "pm2_environment_read=no",
    "NARROWING DECISION GATES",
    "override mariadb.socket as well as preserving Unix socket activation",
    "do not infer that zero point-in-time connections means the service is unused",
    "No database query, grant inspection, service, process, PM2, unit, listener, firewall, WireGuard, configuration, package, client-address, logger, container, or traffic change was performed.",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required consumer-scope behavior: {token}")

prohibited_patterns = (
    r"(?m)^\s*(?:sudo\s+)?(?:mysql|mariadb|mysqladmin|mariadb-admin|mysqldump|mariadb-dump)\b",
    r"(?m)^\s*(?:sudo\s+)?apt(?:-get)?\s+(?:install|upgrade|remove|purge)\b",
    r"(?m)^\s*(?:sudo\s+)?systemctl\s+(?:start|stop|restart|reload|enable|disable|mask|unmask|daemon-reload)\b",
    r"(?m)^\s*(?:sudo\s+)?service\s+\S+\s+(?:start|stop|restart|reload)\b",
    r"(?m)^\s*(?:sudo\s+)?pm2\s+(?:start|stop|restart|reload|delete|save|startup)\b",
    r"(?m)^\s*(?:sudo\s+)?nft\s+(?:add|delete|insert|replace|flush)\b",
    r"(?m)^\s*(?:sudo\s+)?iptables(?:-restore)?(?:\s|$)",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?(?:cp|mv|rm|install|ln|chmod|chown|mkdir)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:strace|gdb|tcpdump|tshark|dumpcap|nmap|masscan|nc|netcat)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:reboot|shutdown|poweroff|halt)\b",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited mutation, query or intrusive command present: {pattern}")

for token in (
    "journalctl",
    "/proc/$pid/environ",
    "/proc/$PID/environ",
    "pm2 jlist",
    "pm2 env",
    "SHOW GRANTS",
    "SELECT ",
    "information_schema",
    "performance_schema",
    "tcpdump",
    "strace -p",
    "gdb -p",
):
    if token in text:
        raise SystemExit(f"sensitive, query, or intrusive behavior present: {token}")

if "ss -Htnp state established" not in text:
    raise SystemExit("scope-only established connection inspection is required")
if "function scope(endpoint)" not in text:
    raise SystemExit("connection endpoints must be reduced to scope classifications")
if "readlink -f" not in text or "stat -L" not in text:
    raise SystemExit("my.cnf symlink and target verification is required")

result = subprocess.run(
    ["sh", "-n", str(SCRIPT)],
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
if result.returncode != 0:
    raise SystemExit(f"shell syntax validation failed: {result.stderr.strip()}")

print("MariaDB UCP consumer scope audit safety validation passed")
