#!/usr/bin/env python3
"""Static safety validation for the focused Asterisk res_odbc path audit."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/security/asterisk_res_odbc_path_audit.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "/etc/asterisk/res_odbc.conf",
    "entry_type=",
    "link_target=",
    "resolved_target=",
    "target_type=",
    "target_mode=",
    "sha256sum",
    "Effective target is group- or world-writable",
    "Audit state: READ-ONLY REVIEW COMPLETE",
    "no configuration contents",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing required behavior: {token}")

prohibited_patterns = (
    r"(?m)^\s*(?:sudo\s+)?(?:mysql|mariadb)\b",
    r"(?m)^\s*(?:sudo\s+)?systemctl\s+(?:start|stop|restart|reload|enable|disable|mask|unmask|daemon-reload)\b",
    r"(?m)^\s*(?:sudo\s+)?service\s+\S+\s+(?:start|stop|restart|reload)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:cp|mv|rm|install|ln|chmod|chown|mkdir|touch)\b",
    r"(?m)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?m)^\s*(?:sudo\s+)?(?:nft|iptables|iptables-restore)\b",
    r"(?m)^\s*(?:sudo\s+)?(?:strace|gdb|tcpdump|tshark|dumpcap|nmap|masscan|nc|netcat)\b",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited mutation or intrusive command present: {pattern}")

for token in (
    "cat $PATH_TO_CHECK",
    "sed -n",
    "grep -",
    "/proc/",
    "journalctl",
    "SHOW PROCESSLIST",
    "SELECT ",
    "GRANT ",
):
    if token in text:
        raise SystemExit(f"content disclosure or query behavior present: {token}")

result = subprocess.run(
    ["sh", "-n", str(SCRIPT)],
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
if result.returncode != 0:
    raise SystemExit(f"shell syntax validation failed: {result.stderr.strip()}")

print("Asterisk res_odbc path audit safety validation passed")
