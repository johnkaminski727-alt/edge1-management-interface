#!/usr/bin/env python3
"""Validate the read-only PJSIP endpoint-policy reconciliation audit."""

from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/telephony/asterisk_pjsip_endpoint_policy_reconciliation.sh"
DOC = ROOT / "docs/telephony/pjsip-endpoint-policy-reconciliation.md"

for path in (SCRIPT, DOC):
    if not path.is_file():
        raise SystemExit(f"missing PJSIP endpoint-policy reconciliation asset: {path.relative_to(ROOT)}")

text = SCRIPT.read_text(encoding="utf-8")
doc = DOC.read_text(encoding="utf-8")

required = (
    "#!/bin/sh",
    "set -eu",
    "--expected-host",
    "--evidence-dir",
    "/var/lib/wwcx-deployment-evidence/asterisk-pjsip-endpoint-policy/",
    "Mode: read-only runtime and generated-configuration reconciliation",
    "core show version",
    "core show uptime",
    "core show channels count",
    "module show like chan_pjsip",
    "module show like res_pjsip",
    "pjsip show endpoints",
    "pjsip show aors",
    "pjsip show contacts",
    "pjsip show transports",
    "parse_endpoint_policy",
    "pjsip-endpoint-policy-summary.txt",
    "generated_endpoint_policy_count",
    "generated_dtmf_mode_rfc4733",
    "generated_dtmf_mode_implicit_rfc4733",
    "endpoint_count_comparison",
    "freepbx_source_content=not_read",
    "freepbx_database_content=not_queried",
    "endpoint_identifiers_retained=no",
    "credential_values_read=no",
    "database_query_performed=no",
    "carrier_interconnect_capability=unverified",
    "call_originated=no",
    "channel_created=no",
    "tone_transmitted=no",
    "runtime_mutation=none",
    "evidence-files.sha256",
    "No channel, call, DTMF transmission, SIP request, database query",
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing endpoint-policy reconciliation behavior: {token}")

prohibited_patterns = (
    r"(?im)^\s*(?:sudo\s+)?systemctl\s+(?:start|stop|restart|reload|enable|disable|mask|unmask)\b",
    r"(?im)^\s*(?:sudo\s+)?service\s+\S+\s+(?:start|stop|restart|reload)\b",
    r"(?im)^\s*(?:sudo\s+)?fwconsole\s+(?:restart|reload|start|stop|ma|chown)\b",
    r"(?im)^\s*(?:sudo\s+)?(?:mysql|mariadb|mysqladmin)\b",
    r"(?im)\b(?:insert|update|delete|replace|alter|drop|truncate|create)\s+(?:into\s+|table\s+|database\s+)",
    r"(?im)^\s*(?:sudo\s+)?(?:apt|apt-get|dpkg|rpm|yum|dnf)\b",
    r"(?im)^\s*(?:sudo\s+)?(?:nft|iptables|ip6tables|ufw)\b",
    r"(?im)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?im)^\s*(?:sudo\s+)?(?:cp|mv|install|rm)\s+[^\n]*(?:/etc/asterisk|/etc/freepbx|/etc/amportal|/var/lib/asterisk)",
    r"(?i)channel\s+originate",
    r"(?i)\bami\s+originate\b",
    r"(?i)\bari\s+.*dtmf",
    r"(?i)\bpjsip\s+send\b",
    r"(?i)\bdialplan\s+reload\b",
    r"(?i)\bmodule\s+(?:load|unload|reload)\b",
    r"(?i)\bcore\s+(?:restart|reload)\b",
)
for pattern in prohibited_patterns:
    if re.search(pattern, text):
        raise SystemExit(f"prohibited live or mutating reconciliation behavior: {pattern}")

sensitive_tokens = (
    "cat /etc/freepbx.conf",
    "cat /etc/amportal.conf",
    "source /etc/freepbx.conf",
    "source /etc/amportal.conf",
    ". /etc/freepbx.conf",
    ". /etc/amportal.conf",
    "grep -R /etc/freepbx.conf",
    "grep -R /etc/amportal.conf",
    "DB_PASS",
    "AMPDBPASS",
)
for token in sensitive_tokens:
    if token in text:
        raise SystemExit(f"credential-bearing FreePBX source inspection present: {token}")

if "sanitize_stream" not in text:
    raise SystemExit("reconciliation audit must sanitize Asterisk CLI output")

for token in (
    "Endpoint:)[[:space:]]+[^[:space:]]+",
    "Aor:)[[:space:]]+[^[:space:]]+",
    "Contact:)[[:space:]]+[^[:space:]]+",
    "Transport:)[[:space:]]+[^[:space:]]+",
    "username|password|secret|auth|outbound_auth",
):
    if token not in text:
        raise SystemExit(f"missing identifier or credential redaction pattern: {token}")

allowed_asterisk_commands = {
    "core show version",
    "core show uptime",
    "core show channels count",
    "module show like chan_pjsip",
    "module show like res_pjsip",
    "pjsip show endpoints",
    "pjsip show aors",
    "pjsip show contacts",
    "pjsip show transports",
}
commands = re.findall(r'capture_asterisk\s+"[^"]+"\s+"([^"]+)"', text)
if set(commands) != allowed_asterisk_commands:
    raise SystemExit(f"unexpected Asterisk CLI allowlist: {sorted(set(commands))}")

syntax = subprocess.run(
    ["sh", "-n", str(SCRIPT)],
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
if syntax.returncode != 0:
    raise SystemExit(f"shell syntax validation failed: {syntax.stderr.strip()}")

required_doc_tokens = (
    "No channel, call, DTMF transmission",
    "runtime PJSIP object visibility",
    "generated `pjsip*.conf` endpoint policy",
    "FreePBX source boundary",
    "does not read `/etc/freepbx.conf`",
    "does not query the FreePBX database",
    "endpoint identifiers are not retained",
    "carrier interoperability remains `unverified`",
    "tools/telephony/asterisk_pjsip_endpoint_policy_reconciliation.sh",
    "/var/lib/wwcx-deployment-evidence/asterisk-pjsip-endpoint-policy/",
    "separate controlled live test",
)
for token in required_doc_tokens:
    if token not in doc:
        raise SystemExit(f"missing endpoint-policy reconciliation documentation boundary: {token}")

print("Asterisk PJSIP endpoint-policy reconciliation validation passed")
