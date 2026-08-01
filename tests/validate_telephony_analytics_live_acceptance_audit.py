#!/usr/bin/env python3
import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "tools" / "telephony" / "telephony_analytics_live_acceptance_audit.sh"

if not AUDIT.is_file():
    raise SystemExit(f"missing analytics live acceptance audit: {AUDIT.relative_to(ROOT)}")

result = subprocess.run(["sh", "-n", str(AUDIT)], check=False)
if result.returncode != 0:
    raise SystemExit("analytics live acceptance audit shell syntax failed")

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
    "payload_validation=passed",
    "privacy_scan=passed",
    "database_query_performed=no",
    "call_origination_performed=no",
    "service_mutation=none",
    "runtime_mutation=none",
    "telephony_analytics_live_acceptance=passed",
):
    if marker not in source:
        raise SystemExit(f"analytics live acceptance audit missing marker: {marker}")

for forbidden in (
    "systemctl start",
    "systemctl restart",
    "systemctl stop",
    "systemctl enable",
    "systemctl disable",
    "systemctl daemon-reload",
    "apt install",
    "dnf install",
    "asterisk -rx",
    "mysql ",
    "psql ",
):
    if forbidden in source:
        raise SystemExit(f"analytics live acceptance audit contains forbidden mutation: {forbidden}")

heredoc = source.split("<<'PY'", 1)[1].split("\nPY\n", 1)[0]
ast.parse(heredoc, filename="embedded-analytics-payload-validation.py")

print("telephony analytics live acceptance audit validation passed")
