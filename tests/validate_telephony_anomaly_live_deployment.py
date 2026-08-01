#!/usr/bin/env python3
"""Validate the bounded telephony anomaly deployment and live audit assets."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy/telephony/telephony-anomaly-api-panel-deploy.sh"
DEPLOY_V2 = ROOT / "deploy/telephony/telephony-anomaly-api-panel-deploy-v2.sh"
AUDIT = ROOT / "tools/telephony/telephony_anomaly_api_panel_live_acceptance_audit.sh"
VALIDATOR = ROOT / "tools/telephony/validate_telephony_analytics_evidence.py"
DOC = ROOT / "docs/telephony/anomaly-api-panel-live-deployment.md"

for path in (DEPLOY, DEPLOY_V2, AUDIT, VALIDATOR, DOC):
    if not path.is_file():
        raise SystemExit(f"missing anomaly deployment asset: {path.relative_to(ROOT)}")

validator_source = VALIDATOR.read_text(encoding="utf-8")
ast.parse(validator_source, filename=str(VALIDATOR))
for marker in (
    "ANOMALY_IDS",
    "ANOMALY_STATES",
    "ANOMALY_TARGETS",
    "ANOMALY_SAFETY_KEYS",
    "validate_anomalies",
    "informational_no_enforcement",
    "automatic_action",
    "platform-anomalies.json",
    "platform-health.anomalies",
    "anomaly_contract=passed",
):
    if marker not in validator_source:
        raise SystemExit(f"analytics evidence validator missing anomaly marker: {marker}")

# The original script remains the analytics-only rollback engine. The v2 wrapper
# performs the required canonical console process refresh before invoking it.
deploy_source = DEPLOY.read_text(encoding="utf-8")
for marker in (
    "#!/bin/bash",
    "set -Eeuo pipefail",
    "--required-commit",
    "/var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-deployment/",
    "GIT_OPTIONAL_LOCKS=0",
    "git_repo merge-base --is-ancestor",
    "analytics-unit-before.service",
    "analytics-unit-candidate.service",
    "trap rollback ERR",
    "AUTOMATIC ROLLBACK",
    'systemctl restart "$ANALYTICS_SERVICE"',
    "console service restart prohibited",
    "telephony_anomaly_api_panel_live_acceptance_audit.sh",
    "analytics_runtime_source=canonical-main",
    "console_service_restart=none",
    "rollback_required=no",
):
    if marker not in deploy_source:
        raise SystemExit(f"analytics deployment engine missing safety marker: {marker}")

for forbidden in (
    'systemctl restart "$CONSOLE_SERVICE"',
    "systemctl restart wwcx-telephony-console.service",
    "git config --global",
    "git reset --hard",
    "git clean",
    "git stash",
    "rm -rf",
    "--host 0.0.0.0",
    "firewall-cmd",
    "nft ",
    "iptables",
):
    if forbidden in deploy_source:
        raise SystemExit(f"analytics deployment engine contains prohibited marker: {forbidden}")

audit_source = AUDIT.read_text(encoding="utf-8")
for marker in (
    "/var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-live-acceptance/",
    "GIT_OPTIONAL_LOCKS=0",
    "runtime_api_source_match",
    "runtime_platform_source_match",
    "runtime_anomaly_source_match",
    "/api/telephony/platform/anomalies",
    "/api/telephony/analytics/health",
    "console_anomaly_contract=passed",
    "index_owner_preserved",
    "telephony_anomaly_api_panel_live_acceptance=passed",
    "notification_dispatch_performed=no",
    "traffic_enforcement_performed=no",
):
    if marker not in audit_source:
        raise SystemExit(f"live audit missing marker: {marker}")

for forbidden in (
    'systemctl restart "$ANALYTICS_SERVICE"',
    'systemctl restart "$CONSOLE_SERVICE"',
    "systemctl stop",
    "systemctl start",
    "systemctl enable",
    "systemctl disable",
    "daemon-reload",
    "git config --global",
    "git reset --hard",
    "git clean",
    "git stash",
    "rm -rf",
):
    if forbidden in audit_source:
        raise SystemExit(f"read-only live audit contains mutation marker: {forbidden}")

doc_source_lower = DOC.read_text(encoding="utf-8").lower()
for marker in (
    "corrected operator entrypoint",
    "2026-08-01 live correction",
    "mutation scope",
    "pre-deployment gates",
    "console refresh verification",
    "automatic analytics rollback",
    "live acceptance",
    "no telephony traffic",
):
    if marker not in doc_source_lower:
        raise SystemExit(f"deployment documentation missing marker: {marker}")

print("telephony anomaly live deployment validation passed")
