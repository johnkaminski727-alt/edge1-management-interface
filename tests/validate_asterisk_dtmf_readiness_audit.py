#!/usr/bin/env python3
"""Validate the read-only Asterisk DTMF readiness audit and offline probe."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "tools/telephony/asterisk_dtmf_readiness_audit.sh"
PROBE = ROOT / "tools/telephony/dtmf_offline_probe.py"
MATRIX = ROOT / "config/telephony/dtmf-capability-matrix.json"
PROVIDER_EVIDENCE_DIR = ROOT / "config/telephony/dtmf-provider-evidence"
PROVIDER_VALIDATOR = ROOT / "tools/telephony/validate_dtmf_provider_evidence.py"
DOC = ROOT / "docs/telephony/dtmf-readiness.md"

for path in (AUDIT, PROBE, MATRIX, PROVIDER_VALIDATOR, DOC):
    if not path.is_file():
        raise SystemExit(f"missing DTMF readiness asset: {path.relative_to(ROOT)}")
if not PROVIDER_EVIDENCE_DIR.is_dir():
    raise SystemExit(
        "missing DTMF provider evidence directory: "
        + str(PROVIDER_EVIDENCE_DIR.relative_to(ROOT))
    )

audit_text = AUDIT.read_text(encoding="utf-8")
probe_text = PROBE.read_text(encoding="utf-8")
doc_text = DOC.read_text(encoding="utf-8")

provider_spec = importlib.util.spec_from_file_location(
    "validate_dtmf_provider_evidence", str(PROVIDER_VALIDATOR)
)
if provider_spec is None or provider_spec.loader is None:
    raise SystemExit("unable to load DTMF provider evidence validator")
provider_validator = importlib.util.module_from_spec(provider_spec)
provider_spec.loader.exec_module(provider_validator)

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

provider_records = {}
for record_path in sorted(PROVIDER_EVIDENCE_DIR.glob("*.json")):
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        provider_validator.validate_record(record)
    except (
        OSError,
        json.JSONDecodeError,
        provider_validator.ValidationError,
    ) as exc:
        raise SystemExit(
            f"invalid DTMF provider evidence record {record_path.relative_to(ROOT)}: {exc}"
        ) from exc
    key = (record["provider_id"], record["route_id"])
    if key in provider_records:
        raise SystemExit(
            "duplicate DTMF provider evidence record for sanitized provider and route"
        )
    provider_records[key] = record

interconnects = matrix.get("interconnects")
if not isinstance(interconnects, list):
    raise SystemExit("DTMF capability matrix interconnects must be an array")

entry_keys = {
    "provider_id",
    "route_id",
    "direction",
    "rfc4733",
    "sip_info",
    "inband",
    "extended_abcd",
    "last_reviewed_at",
    "notes",
}
capability_keys = {
    "rfc4733": {"status", "event_range", "evidence_reference"},
    "sip_info": {"status", "evidence_reference"},
    "inband": {"status", "codec_constraints", "evidence_reference"},
    "extended_abcd": {"status", "evidence_reference"},
}
matrix_keys = set()

for index, entry in enumerate(interconnects):
    location = f"interconnects[{index}]"
    if not isinstance(entry, dict) or set(entry) != entry_keys:
        raise SystemExit(f"{location} has incomplete or unsupported fields")

    provider_id = entry["provider_id"]
    route_id = entry["route_id"]
    for value, field in ((provider_id, "provider_id"), (route_id, "route_id")):
        if not isinstance(value, str) or provider_validator.ID_RE.fullmatch(value) is None:
            raise SystemExit(f"{location}.{field} is not a sanitized identifier")

    key = (provider_id, route_id)
    if key in matrix_keys:
        raise SystemExit(f"duplicate DTMF matrix entry at {location}")
    matrix_keys.add(key)

    record = provider_records.get(key)
    if record is None:
        raise SystemExit(f"{location} lacks a validated provider evidence record")
    if record["decision"]["matrix_eligible"] is not True:
        raise SystemExit(f"{location} references an ineligible provider evidence record")
    if record["decision"]["live_test_authorized"] is not False:
        raise SystemExit(f"{location} provider evidence improperly authorizes a live test")
    if record["decision"]["carrier_interoperability"] == "unverified":
        raise SystemExit(f"{location} has no supported capability for matrix promotion")
    if entry["direction"] != record["direction"]:
        raise SystemExit(f"{location}.direction differs from provider evidence")

    last_reviewed_at = entry["last_reviewed_at"]
    if not isinstance(last_reviewed_at, str) or not last_reviewed_at.endswith("Z"):
        raise SystemExit(f"{location}.last_reviewed_at must be a UTC timestamp")
    if not isinstance(entry["notes"], str) or not entry["notes"].strip():
        raise SystemExit(f"{location}.notes must explain the evidence boundary")

    for name, expected_keys in capability_keys.items():
        matrix_capability = entry[name]
        if not isinstance(matrix_capability, dict) or set(matrix_capability) != expected_keys:
            raise SystemExit(f"{location}.{name} has incomplete or unsupported fields")

        evidence_capability = record["capabilities"][name]
        status = matrix_capability["status"]
        if status != evidence_capability["status"]:
            raise SystemExit(f"{location}.{name}.status differs from provider evidence")

        evidence_reference = matrix_capability["evidence_reference"]
        evidence_refs = evidence_capability["evidence_refs"]
        if status == "unknown":
            if evidence_reference is not None or evidence_refs:
                raise SystemExit(
                    f"{location}.{name} must remain reference-free while unknown"
                )
        elif evidence_reference not in evidence_refs:
            raise SystemExit(
                f"{location}.{name} does not reference supporting provider evidence"
            )

        if name == "rfc4733":
            if matrix_capability["event_range"] != evidence_capability["event_range"]:
                raise SystemExit(
                    f"{location}.rfc4733.event_range differs from provider evidence"
                )
            if status == "documented" and matrix_capability["event_range"] == "unknown":
                raise SystemExit(
                    f"{location}.rfc4733 lacks an evidence-backed event range"
                )
        elif name == "inband":
            if matrix_capability["codec_constraints"] != evidence_capability["codec_constraints"]:
                raise SystemExit(
                    f"{location}.inband codec constraints differ from provider evidence"
                )

eligible_record_keys = {
    key
    for key, record in provider_records.items()
    if record["decision"]["matrix_eligible"] is True
}
if matrix_keys != eligible_record_keys:
    raise SystemExit(
        "DTMF capability matrix entries do not exactly match eligible provider evidence records"
    )

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
