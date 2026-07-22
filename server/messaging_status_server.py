#!/usr/bin/env python3
"""
WW.CX Messaging Operations status server.

Read-only visibility endpoint.
No messaging actions are exposed.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from messaging_gateway_collector import collect_gateway_health


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/messaging/status":
            self.send_response(404)
            self.end_headers()
            return

        payload = collect_gateway_health().to_dict()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        self.wfile.write(
            json.dumps(payload, indent=2).encode("utf-8")
        )

    def log_message(self, *_):
        return


if __name__ == "__main__":
    HTTPServer(
        ("127.0.0.1", 8092),
        Handler
    ).serve_forever()
