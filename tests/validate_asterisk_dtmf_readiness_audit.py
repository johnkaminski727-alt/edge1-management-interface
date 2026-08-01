#!/usr/bin/env python3
"""Validate the read-only Asterisk DTMF readiness audit and offline probe."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "tools/telephony/asterisk_dtmf_readiness_audit.sh"
PROBE = ROOT / "tools/telephony/dtmf_offline_probe.py"
MATRIX = ROOT / "config/telephony/dtmf-capability-matrix.json"
DOC = ROOT / "docs/telephony/dtmf-readiness.md"

for path in (AUDIT, PROBE, MATRIX, DOC):
    if not path.is_file():
        raise SystemExit(f"missing DTMF readiness asset: {path.relative_to(ROOT)}")

audit_text = AUDIT.read_text(encoding="utf-8")
probe_text = PROBE.read_text(encoding="utf-8")
doc_text = DOC.read_text(encoding="utf-8")

required_audit_tokens = (
    "#!/bin/sh",
    "set -eu",
    "--expected-host",
    "--evidence-dir",
    "/var/lib/wwcx-deployment-evidence/asterisk-dtmf-readiness/",
    "core show version",
    "core show uptime",
    "core show channels count",
    "for module_query in app_senddtmf app_playtones app_read func_pjsip res_pjsip_sdp_rtp res_rtp_asterisk dsp; do",
    "module show like $module_query",
    "core show application SendDTMF",
    "core show application Read",
    "core show function PJSIP_DTMF_MODE",
    "core show function PJSIP_ENDPOINT",
    "implicit-rfc4733",
    "rfc4733_event_range=0-15",
    "standard_digits=0-9,*#",
    "extended_digits=A-D",
    "carrier_interconnect_capability=unverified",
    "live_negotiation=not_tested",
    "call_originated=no",
    "channel_created=no",
    "tone_transmitted=no",
    "dtmf_offline_probe.py",
    "offline-dtmf-probe.json",
    "evidence-files.sha256",
    "No channel, call, tone transmission, SIP request",
)
for token in required_audit_tokens:
    if token not in audit_text:
        raise SystemExit(f"missing DTMF audit behavior: {token}")

command_loop = re.search(r"for command in ([^;]+); do", audit_text)
if command_loop is None:
    raise SystemExit("audit lacks an external-command preflight")
required_commands = {
    "asterisk",
    "awk",
    "cat",
    "date",
    "dirname",
    "find",
    "grep",
    "hostname",
    "id",
    "install",
    "mkdir",
    "python3",
    "rm",
    "sed",
    "sha256sum",
    "sort",
    "stat",
    "tail",
    "tr",
    "xargs",
}
observed_commands = set(command_loop.group(1).split())
missing_commands = sorted(required_commands - observed_commands)
if missing_commands:
    raise SystemExit(
        "audit command preflight is incomplete: " + ", ".join(missing_commands)
    )

prohibited_audit_patterns = (
    r"(?im)^\s*(?:sudo\s+)?systemctl\s+(?:start|stop|restart|reload|enable|disable|mask|unmask)\b",
    r"(?im)^\s*(?:sudo\s+)?(?:fwconsole|service)\s+",
    r"(?im)^\s*(?:sudo\s+)?(?:apt|apt-get|dpkg|rpm|yum|dnf)\b",
    r"(?im)^\s*(?:sudo\s+)?(?:nft|iptables|ip6tables|ufw)\b",
    r"(?im)^\s*(?:sudo\s+)?(?:curl|wget|nc|netcat|nmap|masscan|tcpdump|tshark|sngrep)\b",
    r"(?im)^\s*(?:sudo\s+)?sed\s+-i\b",
    r"(?im)^\s*(?:sudo\s+)?(?:cp|mv|install|rm)\s+[^\n]*(?:/etc/asterisk|/var/lib/asterisk|/usr/lib/asterisk)",
    r"(?i)channel\s+originate",
    r"(?i)\bami\s+originate\b",
    r"(?i)\bari\s+.*dtmf",
    r"(?i)\bpjsip\s+send\b",
    r"(?i)\bdialplan\s+reload\b",
    r"(?i)\bmodule\s+(?:load|unload|reload)\b",
    r"(?i)\bcore\s+restart\b",
    r"(?i)\bcore\s+reload\b",
)
for pattern in prohibited_audit_patterns:
    if re.search(pattern, audit_text):
        raise SystemExit(f"prohibited live or mutating audit behavior: {pattern}")

if "cat /etc/asterisk" in audit_text or "sed -n" in audit_text:
    raise SystemExit("audit may expose raw Asterisk configuration content")

if "sanitize_stream" not in audit_text:
    raise SystemExit("audit must sanitize Asterisk CLI output")

if ': >"$EVIDENCE_DIR/asterisk-config-metadata.txt"' not in audit_text:
    raise SystemExit("audit must initialize configuration metadata evidence")
if ': >"$EVIDENCE_DIR/asterisk-config.sha256"' not in audit_text:
    raise SystemExit("audit must initialize configuration hash evidence")

allowed_asterisk_commands = {
    "core show version",
    "core show uptime",
    "core show channels count",
    "core show application SendDTMF",
    "core show application Read",
    "core show function PJSIP_DTMF_MODE",
    "core show function PJSIP_ENDPOINT",
}
for command in re.findall(r'capture_asterisk\s+"[^"]+"\s+"([^"]+)"', audit_text):
    if command.startswith("module show like "):
        continue
    if command not in allowed_asterisk_commands:
        raise SystemExit(f"unapproved Asterisk CLI command: {command}")

syntax = subprocess.run(
    ["sh", "-n", str(AUDIT)],
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
if syntax.returncode != 0:
    raise SystemExit(f"shell syntax validation failed: {syntax.stderr.strip()}")

required_probe_tokens = (
    'ROW_FREQUENCIES: Tuple[int, ...] = (697, 770, 852, 941)',
    'COLUMN_FREQUENCIES: Tuple[int, ...] = (1209, 1336, 1477, 1633)',
    '("1", "2", "3", "A")',
    '("*", "0", "#", "D")',
    '"rfc4733_event_range": "0-15"',
    '"network_access": False',
    '"channel_created": False',
    '"call_originated": False',
)
for token in required_probe_tokens:
    if token not in probe_text:
        raise SystemExit(f"missing offline DTMF probe behavior: {token}")

for forbidden in (
    "import socket",
    "import subprocess",
    "import requests",
    "import urllib",
    "urlopen(",
    "socket.",
    "subprocess.",
    "open(",
):
    if forbidden in probe_text:
        raise SystemExit(f"offline probe contains forbidden I/O behavior: {forbidden}")

probe_run = subprocess.run(
    [sys.executable, str(PROBE), "--json"],
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
if probe_run.returncode != 0:
    raise SystemExit(f"offline DTMF probe failed: {probe_run.stderr.strip()}")

try:
    report = json.loads(probe_run.stdout)
except json.JSONDecodeError as exc:
    raise SystemExit(f"offline DTMF probe emitted invalid JSON: {exc}") from exc

if report.get("audit_state") != "PASS":
    raise SystemExit("offline DTMF probe did not pass")
if report.get("digits_tested") != 16:
    raise SystemExit("offline DTMF probe did not test all 16 keys")
if report.get("digits_expected") != "123A456B789C*0#D":
    raise SystemExit("offline DTMF probe key order is incomplete")
if report.get("network_access") is not False:
    raise SystemExit("offline DTMF probe may access the network")
if report.get("channel_created") is not False:
    raise SystemExit("offline DTMF probe may create a channel")
if report.get("call_originated") is not False:
    raise SystemExit("offline DTMF probe may originate a call")

results = report.get("results")
if not isinstance(results, list) or len(results) != 16:
    raise SystemExit("offline DTMF probe result set is incomplete")
if {entry.get("digit") for entry in results} != set("0123456789*#ABCD"):
    raise SystemExit("offline DTMF probe result digits are incomplete")
if not all(entry.get("passed") is True for entry in results):
    raise SystemExit("one or more offline DTMF probe digits failed")

try:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    raise SystemExit(f"invalid DTMF capability matrix JSON: {exc}") from exc

if matrix.get("schema_version") != 1:
    raise SystemExit("unexpected DTMF capability matrix schema version")
reference = matrix.get("standards_reference", {})
if reference.get("rfc") != "RFC 4733" or reference.get("event_range") != "0-15":
    raise SystemExit("DTMF capability matrix lacks RFC 4733 event range")
if reference.get("event_mapping", {}).get("D") != 15:
    raise SystemExit("DTMF capability matrix lacks extended D event mapping")
if matrix.get("asterisk_endpoint_modes") != [
    "rfc4733",
    "inband",
    "info",
    "auto",
    "auto_info",
]:
    raise SystemExit("DTMF capability matrix endpoint modes are incomplete")
if matrix.get("interconnects") != []:
    raise SystemExit("public repository matrix must not claim unverified carrier paths")
if len(matrix.get("approval_boundaries", [])) < 4:
    raise SystemExit("DTMF capability matrix lacks approval boundaries")

required_doc_tokens = (
    "No channel, call, tone transmission",
    "RFC 4733",
    "events `12-15` to `A-D`",
    "controlled live test",
    "separate production-traffic action",
    "not an emergency-calling path",
    "carrier paths is `unverified`",
    "Do not infer `A-D` support",
    "tools/telephony/asterisk_dtmf_readiness_audit.sh",
    "tools/telephony/dtmf_offline_probe.py",
    "config/telephony/dtmf-capability-matrix.json",
)
for token in required_doc_tokens:
    if token not in doc_text:
        raise SystemExit(f"missing DTMF readiness documentation boundary: {token}")

print("Asterisk DTMF readiness audit validation passed")
