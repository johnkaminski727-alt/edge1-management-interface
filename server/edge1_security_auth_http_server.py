#!/usr/bin/env python3
"""Loopback-only server entrypoint for the Edge1 Security authentication adapter."""
from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .edge1_security_auth_core import GatewayConfig
from .edge1_security_auth_gateway import Edge1SecurityAuthGateway
from .edge1_security_auth_http import Edge1SecurityAuthHttpAdapter, HttpRequest
from .edge1_security_auth_http_config import HttpAdapterConfig

LOOPBACKS = {"127.0.0.1", "::1"}


class Handler(BaseHTTPRequestHandler):
    adapter: Edge1SecurityAuthHttpAdapter
    server_version = "Edge1SecurityAuth/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _dispatch(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > self.adapter.config.maximum_body_bytes:
            response = self.adapter._json(400, {"error": "bad_request"})
        else:
            body = self.rfile.read(length) if length else b""
            headers = {key: value for key, value in self.headers.items()}
            request = HttpRequest(
                method=self.command,
                path=self.path,
                headers=headers,
                body=body,
                remote_addr=str(self.client_address[0]),
                scheme=headers.get("X-Forwarded-Proto", ""),
                host=headers.get("Host", "").split(":", 1)[0],
            )
            response = self.adapter.handle(request)
        self.send_response(response.status)
        has_length = False
        for key, value in response.headers:
            if key.lower() == "content-length":
                has_length = True
            self.send_header(key, value)
        if not has_length:
            self.send_header("Content-Length", str(len(response.body)))
        self.end_headers()
        if response.body:
            self.wfile.write(response.body)

    do_GET = _dispatch
    do_POST = _dispatch
    do_PUT = _dispatch
    do_PATCH = _dispatch
    do_DELETE = _dispatch


def build_adapter() -> Edge1SecurityAuthHttpAdapter:
    root = Path(os.environ.get("EDGE1_SECURITY_AUTH_ROOT", "/opt/edge1-management-interface"))
    gateway_config_path = Path(os.environ.get(
        "EDGE1_SECURITY_AUTH_CONFIG",
        str(root / "config/security/edge1-security-auth-gateway.json"),
    ))
    http_config_path = Path(os.environ.get(
        "EDGE1_SECURITY_AUTH_HTTP_CONFIG",
        str(root / "config/security/edge1-security-auth-http.json"),
    ))
    console_path = Path(os.environ.get(
        "EDGE1_SECURITY_CONSOLE_FILE",
        str(root / "src/web/edge1-ops/security/index.html"),
    ))
    gateway_config = GatewayConfig.from_path(gateway_config_path)
    http_config = HttpAdapterConfig.from_path(http_config_path)
    gateway = Edge1SecurityAuthGateway(gateway_config)
    return Edge1SecurityAuthHttpAdapter(
        http_config,
        gateway,
        console_path=console_path,
    )


def main() -> int:
    adapter = build_adapter()
    host = os.environ.get("EDGE1_SECURITY_AUTH_HOST", "127.0.0.1")
    port = int(os.environ.get("EDGE1_SECURITY_AUTH_PORT", "8108"))
    if host not in LOOPBACKS:
        raise SystemExit("refusing non-loopback bind")
    if not adapter.config.enabled or not adapter.config.deployment_authorized:
        raise SystemExit("HTTP adapter is disabled")
    Handler.adapter = adapter
    ThreadingHTTPServer((host, port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
