#!/usr/bin/env python3
"""Validate the read-only aggregate anomaly API and informational panel."""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = ROOT / "server"
API = SERVER_DIR / "telephony_analytics_api.py"
HTML = ROOT / "src/web/telephony/index.html"
JAVASCRIPT = ROOT / "src/web/telephony/telephony-anomalies.js"
CSS = ROOT / "src/web/telephony/telephony-anomalies.css"
DOC = ROOT / "docs/telephony/anomaly-api-console-panel.md"

for path in (API, HTML, JAVASCRIPT, CSS, DOC):
    if not path.is_file():
        raise SystemExit(f"missing anomaly API/panel asset: {path.relative_to(ROOT)}")

api_source = API.read_text(encoding="utf-8")
ast.parse(api_source, filename=str(API))
for marker in (
    "from telephony_anomaly_indicators import evaluate_anomaly_indicators",
    "def anomaly_payload()",
    "def health_response_payload()",
    'payload["anomalies"] = anomaly_payload()',
    'path == "/api/telephony/platform/anomalies"',
    "METHOD_NOT_ALLOWED",
    "read_only",
):
    if marker not in api_source:
        raise SystemExit(f"analytics API missing anomaly marker: {marker}")

for forbidden in ("do_PUT", "do_PATCH", "do_DELETE", "notification_dispatch(", "systemctl", "subprocess"):
    if forbidden in api_source:
        raise SystemExit(f"analytics anomaly API contains prohibited marker: {forbidden}")

sys.path.insert(0, str(SERVER_DIR))
spec = importlib.util.spec_from_file_location("telephony_analytics_api_anomaly_validation", API)
if spec is None or spec.loader is None:
    raise SystemExit("could not load telephony analytics API")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

health = {
    "score": 80.0,
    "overall_status": "degraded",
    "components": {
        "pbx": "healthy",
        "sip": "degraded",
        "routing": "unknown",
        "registry": "ready",
        "analytics": "healthy",
    },
}
calls = {
    "calls_total": 20,
    "calls_answered": 15,
    "answer_rate_percent": 75.0,
    "duration_seconds_total": 600,
    "duration_seconds_average": 30.0,
    "directions": {"outbound": 20},
    "dispositions": {"answered": 15, "failed": 5},
    "carriers": {"carrier-a": 20},
    "destination_countries": {"CA": 20},
    "sip_codes": {"200": 15, "503": 5},
    "failure_classes": {"server_error": 5},
}
interconnects = {
    "interconnects_total": 2,
    "states": {"healthy": 1, "degraded": 1},
    "latency_ms_average": 200.0,
    "latency_ms_max": 300.0,
    "attention_required": 1,
}

with patch.object(module, "health_payload", return_value=health), \
     patch.object(module, "sanitized_events", return_value=[]), \
     patch.object(module, "interconnect_rows", return_value=[]), \
     patch.object(module, "summarize_calls", return_value=calls), \
     patch.object(module, "analyze_interconnects", return_value=interconnects):
    anomaly = module.anomaly_payload()
    response = module.health_response_payload()

assert response["score"] == 80.0
assert response["anomalies"] == anomaly
assert anomaly["schema_version"] == "1.0"
assert anomaly["mode"] == "informational_no_enforcement"
assert len(anomaly["indicators"]) == 6
assert all(item["automatic_action"] is False for item in anomaly["indicators"])
assert anomaly["safety"] == {
    "automatic_action": False,
    "notification_dispatch": False,
    "traffic_enforcement": False,
    "route_change": False,
    "service_control": False,
}

html = HTML.read_text(encoding="utf-8")
for marker in (
    'id="analytics-anomalies"',
    'class="analytics-card analytics-anomaly-card"',
    'src="./telephony-anomalies.js"',
    'href="./telephony-anomalies.css"',
    'aria-live="polite"',
):
    if marker not in html:
        raise SystemExit(f"anomaly panel HTML missing marker: {marker}")

javascript = JAVASCRIPT.read_text(encoding="utf-8")
for marker in (
    "'/api/telephony/analytics/health'",
    "informational_no_enforcement",
    "EXPECTED_IDS",
    "SAFETY_KEYS",
    "TARGETS",
    "indicator.automatic_action !== false",
    "escapeHtml",
    "invalid anomaly contract",
    "No notification, enforcement, routing, service control, or automatic remediation.",
):
    if marker not in javascript:
        raise SystemExit(f"anomaly panel JavaScript missing marker: {marker}")

for forbidden in (
    "127.0.0.1:8099",
    "localhost:8099",
    "/api/telephony/platform/",
    "fetch('http://",
    'fetch("http://',
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "window.location",
    "innerHTML = health",
):
    if forbidden in javascript:
        raise SystemExit(f"anomaly panel JavaScript contains prohibited marker: {forbidden}")

css = CSS.read_text(encoding="utf-8")
for marker in (
    ".analytics-anomaly-card",
    ".anomaly-indicators",
    ".anomaly-indicator",
    ".anomaly-ok",
    ".anomaly-watch",
    ".anomaly-critical",
    ".anomaly-insufficient_data",
):
    if marker not in css:
        raise SystemExit(f"anomaly panel CSS missing marker: {marker}")

doc = DOC.read_text(encoding="utf-8")
for marker in (
    "Existing same-origin route",
    "Dedicated loopback route",
    "Fail-closed browser validation",
    "No deployment in this increment",
):
    if marker not in doc:
        raise SystemExit(f"anomaly API/panel documentation missing marker: {marker}")

print("telephony anomaly API and console panel validation passed")
