#!/usr/bin/env python3
"""Static safety validation for the atomic MariaDB loopback socket operator."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/security/apply_mariadb_loopback_socket_hardening.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "EDGE1_ALLOW_CONDITIONAL",
    "--apply",
    "--evidence-dir",
    "/var/lib/wwcx-deployment-evidence/mariadb-loopback-hardening/",
    "EXPECTED_SOURCE_SHA=c5365e2d9bd882fcf62a8676b98f8f996094c5b5e45572fe9a0244b7f4f32fea",
    "mariadb_loopback_socket_preflight_audit.sh",
    "asterisk_res_odbc_path_audit.sh",
    "0 active channels",
    "0 active calls",
    "10-loopback-only.conf.before",
    "dropin-was-absent",
    "ROLLBACK_ARMED=1",
    "restore_previous_dropin",
    "systemctl daemon-reload",
    "systemd-analyze verify mariadb.socket mariadb.service",
    "systemctl stop mariadb.service mariadb.socket",
    "systemctl start mariadb.socket",
    "systemctl start mariadb.service",
    "127\\.0\\.0\\.1:3306",
    "\\[::1\\]:3306",
    "/run/mysqld/mysqld.sock",
    "@mariadb",
    "ucp_contract_ok",
    "ucp_loopback_connection_reestablished",
    "users:\\\\(\\\\(\\\\\"node",
    "journal-after.txt",
    "CHANGE APPLIED AND VERIFIED",
    "CHANGE FAILED AND ROLLED BACK",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required activation safety behavior: {token}")

prohibited_patterns = (
    r"(?m)^\s*(?:sudo\s+)?(?:mysql|mariadb)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:apt|apt-get|dpkg|rpm|yum|dnf)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:nft|iptables|ip6tables|ufw)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:curl|wget)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:strace|gdb|tcpdump|tshark|dumpcap|nmap|masscan|nc|netcat)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:pm2|fwconsole)\b",
    r"(?m)^\s*(?:sudo\s+)?systemctl\s+(?:start|stop|restart|reload)\s+(?:freepbx|asterisk)(?:\.service)?\b",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?(?:vi|vim|nano|ed)\b",
    r"(?i)\b(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|GRANT|REVOKE|TRUNCATE)\b",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited command or SQL behavior present: {pattern}")

for token in (
    "/proc/$pid/environ",
    "process.env",
    "pm2 env",
    "SHOW PROCESSLIST",
    "EDGE1_ALLOW_CONDITIONAL=1" + "\nexport",
    "/lib/systemd/system/mariadb.socket\"",
):
    if token in text:
        raise SystemExit(f"sensitive or unsafe activation behavior present: {token}")

asterisk_commands = re.findall(r"asterisk\s+-rx\s+'([^']+)'", text)
allowed_asterisk_commands = {"core show uptime", "core show channels count"}
if not asterisk_commands:
    raise SystemExit("missing bounded Asterisk health checks")
if any(command not in allowed_asterisk_commands for command in asterisk_commands):
    raise SystemExit(f"unapproved Asterisk command present: {asterisk_commands}")

rm_commands = [line.strip() for line in text.splitlines() if re.match(r"^\s*rm\b", line)]
if rm_commands != ['rm -f "$DROPIN"']:
    raise SystemExit(f"unexpected rm scope: {rm_commands}")

if "find \"$EVIDENCE_DIR\" -maxdepth 1 -type f ! -name 'evidence-files.sha256'" not in text:
    raise SystemExit("evidence hash manifest must exclude itself")

result = subprocess.run(
    ["sh", "-n", str(SCRIPT)],
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
if result.returncode != 0:
    raise SystemExit(f"shell syntax validation failed: {result.stderr.strip()}")

print("Atomic MariaDB loopback socket hardening validation passed")
