#!/usr/bin/env python3
"""WW.CX Messaging Operations local status server.

Exposes read-only health, diagnostics, and history endpoints plus a deterministic
sandbox simulation endpoint. It contains no live SMS/MMS or carrier delivery
capability.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from messaging_diagnostics import build_diagnostics
from messaging_gateway_collector import collect_gateway_health
from messaging_history import latest_snapshot, list_snapshots, record_snapshot
from messaging_sandbox import simulate_message

HOST = "127.0.0.1"
PORT = 8092
MAX_REQUEST_BYTES = 16_384


class Handler(BaseHTTPRequestHandler):
    def _write_json(self, status: int, payload: object) -> None:
        encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/messaging/status":
            snapshot = collect_gateway_health().to_dict()
            record_snapshot(snapshot)
            self._write_json(200, snapshot)
            return

        if parsed.path == "/messaging/diagnostics":
            snapshot = collect_gateway_health().to_dict()
            self._write_json(200, build_diagnostics(snapshot))
            return

        if parsed.path == "/messaging/history":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["25"])[0])
            except ValueError:
                self._write_json(400, {"error": "limit must be an integer"})
                return
            self._write_json(200, {"snapshots": list_snapshots(limit=limit)})
            return

        if parsed.path == "/messaging/history/latest":
            self._write_json(200, {"snapshot": latest_snapshot()})
            return

        self._write_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/messaging/sandbox/simulate":
            self._write_json(404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._write_json(400, {"error": "invalid content length"})
            return

        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._write_json(413, {"error": "request body size is invalid"})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._write_json(400, {"error": "request body must be valid JSON"})
            return

        if not isinstance(payload, dict):
            self._write_json(400, {"error": "request body must be an object"})
            return

        result = simulate_message(payload)
        self._write_json(200 if result["accepted"] else 422, result)

    def log_message(self, *_: object) -> None:
        return


if __name__ == "__main__":
    HTTPServer((HOST, PORT), Handler).serve_forever()
