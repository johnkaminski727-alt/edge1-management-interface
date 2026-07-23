#!/usr/bin/env python3
"""Loopback-only read-only API for aggregate telephony analytics."""
from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from telephony_platform import CallEvent, analyze_interconnects, health_score, summarize_calls

REPO_ROOT = Path(__file__).resolve().parents[1]
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
CALL_EVENTS_PATH = REPO_ROOT / "data/telephony/analytics/call-events.sanitized.json"
INTERCONNECT_PATH = REPO_ROOT / "data/registry/interconnect/status/peer-status.json"


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def sanitized_events() -> list[CallEvent]:
    raw = load_json(CALL_EVENTS_PATH)
    if not isinstance(raw, list):
        return []
    events: list[CallEvent] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            events.append(CallEvent(
                direction=str(item.get("direction", "unknown")),
                disposition=str(item.get("disposition", "unknown")),
                sip_code=item.get("sip_code") if isinstance(item.get("sip_code"), int) else None,
                carrier_id=str(item["carrier_id"]) if item.get("carrier_id") else None,
                destination_country=str(item["destination_country"]) if item.get("destination_country") else None,
                duration_seconds=int(item.get("duration_seconds", 0)),
            ))
        except (TypeError, ValueError):
            continue
    return events


def interconnect_rows() -> list[dict[str, Any]]:
    raw = load_json(INTERCONNECT_PATH)
    peers = raw.get("peers", {}) if isinstance(raw, dict) else {}
    rows: list[dict[str, Any]] = []
    for peer_id, value in peers.items():
        if not isinstance(value, dict):
            continue
        options = value.get("sip_options", {}) if isinstance(value.get("sip_options"), dict) else {}
        rows.append({
            "id": str(peer_id),
            "status": str(value.get("status", "unknown")),
            "latency_ms": options.get("latency_ms"),
        })
    return rows


def health_payload() -> dict[str, Any]:
    interconnects = interconnect_rows()
    interconnect_summary = analyze_interconnects(interconnects)
    sip_state = "healthy" if interconnect_summary["attention_required"] == 0 and interconnects else (
        "degraded" if interconnects else "unknown"
    )
    analytics_state = "healthy" if CALL_EVENTS_PATH.is_file() else "unknown"
    return health_score({
        "pbx": "unknown",
        "sip": sip_state,
        "routing": "unknown",
        "registry": "ready" if INTERCONNECT_PATH.is_file() else "unknown",
        "analytics": analytics_state,
    })


class Handler(BaseHTTPRequestHandler):
    server_version = "WWCXTelephonyAnalytics/0.1"

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/healthz":
            self.send_json(HTTPStatus.OK, {"status": "ok", "mode": "read_only"})
        elif path == "/api/telephony/platform/health":
            self.send_json(HTTPStatus.OK, health_payload())
        elif path == "/api/telephony/platform/calls/summary":
            self.send_json(HTTPStatus.OK, summarize_calls(sanitized_events()))
        elif path == "/api/telephony/platform/interconnects/summary":
            self.send_json(HTTPStatus.OK, analyze_interconnects(interconnect_rows()))
        else:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        self.send_json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "read_only"})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_json(self, status: HTTPStatus, value: Any) -> None:
        body = json.dumps(value, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()
    if args.host not in LOOPBACK_HOSTS:
        parser.error("telephony analytics API must remain loopback-only")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
