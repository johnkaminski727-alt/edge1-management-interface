#!/usr/bin/env python3
"""Validate the bounded console-refresh wrapper for anomaly deployment."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/telephony/telephony-anomaly-api-panel-deploy-v2.sh"
DOC = ROOT / "docs/telephony/anomaly-api-panel-console-refresh.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    require(SCRIPT.is_file(), f"missing {SCRIPT.relative_to(ROOT)}")
    require(DOC.is_file(), f"missing {DOC.relative_to(ROOT)}")

    script = SCRIPT.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")

    required_script_markers = (
        "#!/bin/bash",
        "set -Eeuo pipefail",
        'EXPECTED_HOST="edge1.ww.cx"',
        'CONSOLE_SERVICE="wwcx-telephony-console.service"',
        'CONSOLE_URL="http://127.0.0.1:8096"',
        'systemctl restart "$CONSOLE_SERVICE"',
        'CONSOLE_PID_AFTER',
        'CONSOLE_PID_BEFORE',
        '/api/telephony/analytics/health',
        '[ "$PROXY_CODE" = "200" ]',
        'python3 -m json.tool "$CONSOLE_EVID/analytics-health-after.json"',
        'bash "$ANALYTICS_DEPLOY"',
        'telephony-anomaly-api-panel-deploy.sh',
        'console_recovery_health=passed',
        'console_service_restart=completed',
        'console_proxy_route=passed',
        'analytics_rollback_required=no',
        'GIT_OPTIONAL_LOCKS=0',
        '127\\.0\\.0\\.1:8096',
        '0\\.0\\.0\\.0:8096',
        'repository-status-after.txt',
        'evidence-manifest.sha256',
    )
    for marker in required_script_markers:
        require(marker in script, f"console refresh wrapper missing marker: {marker}")

    require(script.count('systemctl restart "$CONSOLE_SERVICE"') >= 2,
            "console refresh wrapper must include restart and bounded recovery")
    require('systemctl restart "$ANALYTICS_SERVICE"' not in script,
            "wrapper must delegate analytics mutation to the accepted deployment engine")

    prohibited = (
        "git reset",
        "git clean",
        "git stash",
        "git config --global",
        "iptables",
        "nft ",
        "ufw ",
        "firewall-cmd",
        "asterisk -rx",
        "pjsip",
        "originate",
        "sendmail",
        "systemctl stop",
        "systemctl disable",
        "0.0.0.0 --port 8096",
    )
    for marker in prohibited:
        require(marker not in script, f"console refresh wrapper contains prohibited operation: {marker}")

    required_doc_markers = (
        "2026-08-01 live finding",
        "HTTP 404",
        "stale in-memory route map",
        "console restart",
        "analytics rollback",
        "loopback-only",
        "No calls",
    )
    for marker in required_doc_markers:
        require(marker.lower() in doc.lower(), f"console refresh documentation missing marker: {marker}")

    print("telephony anomaly console refresh validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
