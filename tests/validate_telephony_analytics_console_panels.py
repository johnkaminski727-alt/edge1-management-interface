#!/usr/bin/env python3
"""Validate read-only aggregate analytics panels and exact same-origin proxy routes."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server" / "telephony_status_server.py"
HTML = ROOT / "src" / "web" / "telephony" / "index.html"
JAVASCRIPT = ROOT / "src" / "web" / "telephony" / "telephony.js"
CSS = ROOT / "src" / "web" / "telephony" / "telephony.css"
DOC = ROOT / "docs" / "telephony" / "analytics-console-panels.md"

for path in (SERVER, HTML, JAVASCRIPT, CSS, DOC):
    if not path.is_file():
        raise SystemExit(f"missing analytics console panel asset: {path.relative_to(ROOT)}")

server_source = SERVER.read_text(encoding="utf-8")
ast.parse(server_source, filename=str(SERVER))

spec = importlib.util.spec_from_file_location("telephony_status_server_validation", SERVER)
if spec is None or spec.loader is None:
    raise SystemExit("could not load telephony status server for validation")
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)

expected_routes = {
    "/api/telephony/analytics/health": "/api/telephony/platform/health",
    "/api/telephony/analytics/calls": "/api/telephony/platform/calls/summary",
    "/api/telephony/analytics/interconnects": "/api/telephony/platform/interconnects/summary",
}
assert server_module.ANALYTICS_BASE_URL == "http://127.0.0.1:8099"
assert server_module.ANALYTICS_ROUTE_MAP == expected_routes

for marker in (
    "analytics_path = ANALYTICS_ROUTE_MAP.get(path)",
    "payload = http_json(ANALYTICS_BASE_URL + analytics_path)",
    'HTTPStatus.SERVICE_UNAVAILABLE, {"error": "analytics_unavailable"}',
    "return",
):
    if marker not in server_source:
        raise SystemExit(f"telephony status server missing analytics proxy marker: {marker}")

for forbidden in (
    "ANALYTICS_BASE_URL + path",
    "self.path.startswith('/api/telephony/analytics')",
    "urllib.parse",
    "urljoin(",
    "do_POST",
    "/api/telephony/analytics/write",
    "/api/telephony/analytics/config",
):
    if forbidden in server_source:
        raise SystemExit(f"telephony analytics proxy contains unsafe or write-capable marker: {forbidden}")

html_source = HTML.read_text(encoding="utf-8")
for marker in (
    'id="analytics-title"',
    'id="analytics-health"',
    'id="analytics-failures"',
    'id="analytics-carriers"',
    'aria-live="polite"',
    "Privacy-minimized summaries from the loopback analytics API.",
):
    if marker not in html_source:
        raise SystemExit(f"telephony analytics panel HTML missing marker: {marker}")

javascript = JAVASCRIPT.read_text(encoding="utf-8")
for marker in (
    "/api/telephony/analytics/health",
    "/api/telephony/analytics/calls",
    "/api/telephony/analytics/interconnects",
    "Promise.allSettled",
    "renderAnalyticsHealth",
    "renderAnalyticsFailures",
    "renderAnalyticsCarriers",
    "analyticsUnavailable",
    "replace(/[&<>\"']/g",
    "No failure classes observed in the sanitized dataset.",
    "Sanitized carrier utilization",
):
    if marker not in javascript:
        raise SystemExit(f"telephony analytics panel JavaScript missing marker: {marker}")

for forbidden in (
    "127.0.0.1:8099",
    "localhost:8099",
    "fetch('http://",
    'fetch("http://',
    "/api/telephony/platform/",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
):
    if forbidden in javascript:
        raise SystemExit(f"browser analytics code contains prohibited direct or write access: {forbidden}")

css_source = CSS.read_text(encoding="utf-8")
for marker in (
    ".analytics-section",
    ".analytics-grid",
    ".analytics-card",
    ".analytics-score",
    ".analytics-stats",
    ".analytics-list",
    ".analytics-unavailable",
):
    if marker not in css_source:
        raise SystemExit(f"telephony analytics panel CSS missing marker: {marker}")

doc_source = DOC.read_text(encoding="utf-8")
for marker in (
    "Exact same-origin routes",
    "Privacy-minimized panels",
    "Failure behavior",
    "No deployment in this increment",
):
    if marker not in doc_source:
        raise SystemExit(f"analytics console panel documentation missing marker: {marker}")

print("telephony analytics console panel validation passed")
