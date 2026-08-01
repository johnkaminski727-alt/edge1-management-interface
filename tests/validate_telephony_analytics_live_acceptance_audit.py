#!/usr/bin/env python3
import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "tools" / "telephony" / "telephony_analytics_live_acceptance_audit.sh"
PAYLOAD_VALIDATOR = ROOT / "tools" / "telephony" / "validate_telephony_analytics_evidence.py"

for path in (AUDIT, PAYLOAD_VALIDATOR):
    if not path.is_file():
        raise SystemExit(f"missing analytics live acceptance asset: {path.relative_to(ROOT)}")

if subprocess.run(["sh", "-n", str(AUDIT)], check=False).returncode != 0:
    raise SystemExit("analytics live acceptance audit shell syntax failed")
ast.parse(PAYLOAD_VALIDATOR.read_text(encoding="utf-8"), filename=str(PAYLOAD_VALIDATOR))

source = AUDIT.read_text(encoding="utf-8")
for marker in (
    "/var/lib/wwcx-deployment-evidence/telephony-analytics-live-acceptance/",
    "http://127.0.0.1:8099",
    "wwcx-telephony-analytics.service",
    "/api/telephony/platform/health",
    "/api/telephony/platform/calls/summary",
    "/api/telephony/platform/interconnects/summary",
    "POST method boundary",
    "unsafe wildcard listener",
    "validate_telephony_analytics_evidence.py",
    "safe.directory=",
    "database_query_performed=no",
    "call_origination_performed=no",
    "service_mutation=none",
    "runtime_mutation=none",
    "telephony_analytics_live_acceptance=passed",
):
    if marker not in source:
        raise SystemExit(f"analytics live acceptance audit missing marker: {marker}")

for forbidden in (
    "systemctl start", "systemctl restart", "systemctl stop", "systemctl enable",
    "systemctl disable", "systemctl daemon-reload", "apt install", "dnf install",
    "asterisk -rx", "mysql ", "psql ", "git config --global",
):
    if forbidden in source:
        raise SystemExit(f"analytics live acceptance audit contains forbidden mutation: {forbidden}")

validator_source = PAYLOAD_VALIDATOR.read_text(encoding="utf-8")
for marker in (
    "payload_validation=passed", "privacy_scan=passed", "PROHIBITED_KEYS",
    "calls-summary.json", "interconnects-summary.json", "post-response.json",
):
    if marker not in validator_source:
        raise SystemExit(f"analytics evidence validator missing marker: {marker}")

print("telephony analytics live acceptance audit validation passed")
