#!/usr/bin/env python3
"""Static safety validation for the MariaDB loopback socket preflight."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/security/mariadb_loopback_socket_preflight_audit.sh"
CANDIDATE = ROOT / "templates/systemd/mariadb.socket.d/10-loopback-only.conf"

text = SCRIPT.read_text(encoding="utf-8")
candidate = CANDIDATE.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "WW.CX MARIADB LOOPBACK SOCKET HARDENING PREFLIGHT",
    "Mode: read-only",
    "CANDIDATE CONTRACT",
    "CURRENT SYSTEMD CONTRACT",
    "CURRENT TCP AND UNIX LISTENERS",
    "CORRECTED CONNECTION SCOPE",
    "non_loopback_count=",
    "mariadb_connection_pids=",
    "TRANSPORT CANDIDATES",
    "ucp_change_authorized=no",
    "READ-ONLY PREFLIGHT PASSED",
    'sub(/^"/, "", token);',
    'sub(/".*$/, "", token);',
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required preflight behavior: {token}")

expected_listeners = [
    "ListenStream=",
    "ListenStream=@mariadb",
    "ListenStream=/run/mysqld/mysqld.sock",
    "ListenStream=127.0.0.1:3306",
    "ListenStream=[::1]:3306",
]
actual_listeners = [line.strip() for line in candidate.splitlines() if line.startswith("ListenStream=")]
if actual_listeners != expected_listeners:
    raise SystemExit(f"unexpected candidate listener contract: {actual_listeners!r}")

if "[Socket]" not in candidate:
    raise SystemExit("candidate drop-in has no [Socket] section")
if "DO NOT INSTALL" not in candidate:
    raise SystemExit("candidate lacks design-only warning")

prohibited_patterns = (
    r"(?m)^\s*(?:sudo\s+)?(?:mysql|mariadb)\b",
    r"(?m)^\s*(?:sudo\s+)?systemctl\s+(?:start|stop|restart|reload|enable|disable|mask|unmask|daemon-reload)\b",
    r"(?m)^\s*(?:sudo\s+)?service\s+\S+\s+(?:start|stop|restart|reload)\b",
    r"(?m)^\s*(?:sudo\s+)?nft\s+(?:add|delete|insert|replace|flush)\b",
    r"(?m)^\s*(?:sudo\s+)?iptables(?:-restore)?(?:\s|$)",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?(?:cp|mv|rm|install|ln|chmod|chown|mkdir|touch)\b",
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

if "$4 ~ /:3306$/ || $5 ~ /:3306$/" in text:
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

print("MariaDB loopback socket preflight safety validation passed")
