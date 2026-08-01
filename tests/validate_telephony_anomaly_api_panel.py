#!/usr/bin/env python3
"""Validate the read-only anomaly endpoint, exact proxy, and console panel."""
from __future__ import annotations

import ast
import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "server" / "telephony_analytics_api.py"
STATUS_SERVER = ROOT / "server" / "telephony_status_server.py"
HTML = ROOT / "src" / "web" / "telephony" / "index.html"
JAVASCRIPT = ROOT / "src" / "web" / "telephony" / "telephony.js"
CSS = ROOT / "src" / "web" / "telephony" / "telephony.css"
DOC = ROOT / "docs" / "telephony" / "anomaly-api-console-panel.md"

for path in (API, STATUS_SERVER, HTML, JAVASCRIPT, CSS, DOC):
    if not path.is_file():
        raise SystemExit(f"missing anomaly API/panel asset: {path.relative_to(ROOT)}")

for source_path in (API, STATUS_SERVER):
    ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

spec = importlib.util.spec_from_file_location("telephony_status_server_anomaly_validation", STATUS_SERVER)
if spec is None or spec.loader is None:
    raise SystemExit("could not load telephony status server")
status_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status_module)

assert status_module.ANALYTICS_ROUTE_MAP == {
    "/api/telephony/analytics/health": "/api/telephony/platform/health",
    "/api/telephony/analytics/calls": "/api/telephony/platform/calls/summary",
    "/api/telephony/analytics/interconnects": "/api/telephony/platform/interconnects/summary",
}
assert status_module.ANOMALY_ROUTE == "/api/telephony/analytics/anomalies"
assert status_module.ANOMALY_UPSTREAM_PATH == "/api/telephony/platform/anomalies"

status_source = STATUS_SERVER.read_text(encoding="utf-8")
for marker in (
    "if path == ANOMALY_ROUTE:",
    "payload = http_json(ANALYTICS_BASE_URL + ANOMALY_UPSTREAM_PATH)",
    'HTTPStatus.SERVICE_UNAVAILABLE, {"error": "anomalies_unavailable"}',
):
    if marker not in status_source:
        raise SystemExit(f"status server missing anomaly proxy marker: {marker}")
for forbidden in (
    "ANOMALY_UPSTREAM_PATH + path",
    "self.path.startswith('/api/telephony/analytics/anomalies')",
    "anomaly_url =",
    "do_POST",
):
    if forbidden in status_source:
        raise SystemExit(f"status server anomaly route contains unsafe marker: {forbidden}")

api_source = API.read_text(encoding="utf-8")
for marker in (
    "/api/telephony/platform/anomalies",
    "evaluate_anomaly_indicators",
    '"anomaly_indicators"',
    "METHOD_NOT_ALLOWED",
):
    if marker not in api_source:
        raise SystemExit(f"analytics API missing anomaly marker: {marker}")

html_source = HTML.read_text(encoding="utf-8")
for marker in (
    'id="analytics-anomalies"',
    "Informational review indicators",
    "Loading bounded indicators",
    'aria-live="polite"',
):
    if marker not in html_source:
        raise SystemExit(f"anomaly panel HTML missing marker: {marker}")

javascript = JAVASCRIPT.read_text(encoding="utf-8")
for marker in (
    "/api/telephony/analytics/anomalies",
    "renderAnalyticsAnomalies",
    "validAnomalyPayload",
    "informational_no_enforcement",
    "investigationTargets",
    "indicatorLabels",
    "No automatic action, notification, traffic enforcement, route change, or service control.",
    "safety.automatic_action !== false",
    "safety.notification_dispatch !== false",
    "safety.traffic_enforcement !== false",
    "safety.route_change !== false",
    "safety.service_control !== false",
    "indicator.automatic_action === false",
):
    if marker not in javascript:
        raise SystemExit(f"anomaly panel JavaScript missing marker: {marker}")
for marker in (
    "'#analytics-health'",
    "'#analytics-failures'",
    "'#analytics-carriers'",
):
    if marker not in javascript:
        raise SystemExit(f"anomaly panel missing static investigation target: {marker}")
for forbidden in (
    "127.0.0.1:8099",
    "localhost:8099",
    "/api/telephony/platform/anomalies",
    "fetch('http://",
    'fetch("http://',
    "notification_dispatch: true",
    "traffic_enforcement: true",
    "route_change: true",
    "service_control: true",
):
    if forbidden in javascript:
        raise SystemExit(f"anomaly panel contains prohibited browser/action marker: {forbidden}")

css_source = CSS.read_text(encoding="utf-8")
for marker in (
    ".anomaly-summary",
    ".analytics-mode-note",
    ".indicator-list",
    ".indicator-value",
):
    if marker not in css_source:
        raise SystemExit(f"anomaly panel CSS missing marker: {marker}")

node = subprocess.run(
    ["node", "--check", str(JAVASCRIPT)],
    cwd=str(ROOT),
    check=False,
    capture_output=True,
    text=True,
)
if node.returncode != 0:
    raise SystemExit(node.stderr or "telephony JavaScript syntax check failed")

doc_source = DOC.read_text(encoding="utf-8")
for marker in (
    "Separate exact proxy route",
    "Strict payload acceptance",
    "Static investigation anchors",
    "No notification or enforcement",
    "No runtime deployment",
):
    if marker not in doc_source:
        raise SystemExit(f"anomaly API/panel documentation missing marker: {marker}")

print("telephony anomaly API and panel validation passed")
