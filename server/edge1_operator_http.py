#!/usr/bin/env python3
"""Loopback-only MCP Streamable HTTP transport for the bounded Edge1 Operator.

The transport exposes only the pre-registered MCP dispatcher methods. It does
not accept command names, argv, paths, URLs, service names, or other execution
parameters beyond the typed MCP tool contract already enforced by the adapter.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import stat
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

PROTOCOL_VERSION = "2025-11-25"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8098
DEFAULT_PATH = "/mcp"
MAX_BODY = 1024 * 1024


class TransportConfigError(RuntimeError):
    pass


def _is_loopback_host(host: str) -> bool:
    return host in {"127.0.0.1", "::1", "localhost"}


def load_bearer_token(path: Path) -> str:
    try:
        st = path.stat()
    except OSError as exc:
        raise TransportConfigError("MCP token file is unavailable") from exc
    if not stat.S_ISREG(st.st_mode):
        raise TransportConfigError("MCP token path must be a regular file")
    if st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise TransportConfigError("MCP token file must not be accessible by group/other")
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise TransportConfigError("MCP token file could not be read") from exc
    if len(token) < 32:
        raise TransportConfigError("MCP bearer token must be at least 32 characters")
    if any(ch.isspace() for ch in token):
        raise TransportConfigError("MCP bearer token must not contain whitespace")
    return token


def allowed_origins_from_env(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()
    origins = {item.strip() for item in value.split(",") if item.strip()}
    for origin in origins:
        if not (origin.startswith("https://") or origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost")):
            raise TransportConfigError("allowed Origin must use HTTPS or loopback HTTP")
    return frozenset(origins)


def jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def jsonrpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def mcp_tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    is_error = payload.get("status") != "ok"
    safe_payload = {
        "tool": payload.get("tool"),
        "status": payload.get("status"),
        "payload": payload.get("payload"),
    }
    return {
        "content": [{"type": "text", "text": json.dumps(safe_payload, sort_keys=True, separators=(",", ":"))}],
        "structuredContent": safe_payload,
        "isError": is_error,
    }


def dispatch_mcp(operator: Any, message: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
    if message.get("jsonrpc") != "2.0":
        return 400, jsonrpc_error(message.get("id"), -32600, "Invalid Request")
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}
    if not isinstance(params, dict):
        return 400, jsonrpc_error(request_id, -32602, "Invalid params")

    if method == "notifications/initialized":
        if request_id is not None:
            return 400, jsonrpc_error(request_id, -32600, "Initialized must be a notification")
        return 202, None

    if request_id is None:
        return 202, None

    if method == "initialize":
        requested = params.get("protocolVersion")
        if not isinstance(requested, str):
            return 200, jsonrpc_error(request_id, -32602, "protocolVersion is required")
        return 200, jsonrpc_result(request_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "wwcx-edge1-operator", "version": "1"},
            "instructions": "Private bounded Edge1 operations. Only named parameterless tools are exposed.",
        })

    if method == "ping":
        return 200, jsonrpc_result(request_id, {})

    if method == "tools/list":
        if params:
            unsupported = set(params) - {"cursor", "_meta"}
            if unsupported:
                return 200, jsonrpc_error(request_id, -32602, "Unsupported tools/list params")
        try:
            result = operator.handle(type("Request", (), {"method": "tools/list", "payload": {}})()).result
        except Exception:
            return 200, jsonrpc_error(request_id, -32603, "Internal error")
        return 200, jsonrpc_result(request_id, result)

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return 200, jsonrpc_error(request_id, -32602, "Invalid tools/call params")
        unsupported = set(params) - {"name", "arguments", "_meta"}
        if unsupported:
            return 200, jsonrpc_error(request_id, -32602, "Unsupported tools/call params")
        try:
            result = operator.handle(type("Request", (), {
                "method": "tools/call",
                "payload": {"name": name, "arguments": arguments},
            })()).result
        except Exception:
            return 200, jsonrpc_error(request_id, -32603, "Internal error")
        return 200, jsonrpc_result(request_id, mcp_tool_result(result))

    return 200, jsonrpc_error(request_id, -32601, "Method not found")


def make_handler(operator: Any, token: str, allowed_origins: frozenset[str], endpoint: str = DEFAULT_PATH):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Edge1MCP/1"

        def log_message(self, fmt: str, *args: Any) -> None:
            super().log_message(fmt, *args)

        def _common_checks(self) -> bool:
            if self.path != endpoint:
                self.send_error(404)
                return False
            origin = self.headers.get("Origin")
            if origin is not None and origin not in allowed_origins:
                self.send_error(403)
                return False
            auth = self.headers.get("Authorization", "")
            expected = f"Bearer {token}"
            if not hmac.compare_digest(auth, expected):
                self.send_response(401)
                self.send_header("WWW-Authenticate", "Bearer")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return False
            return True

        def do_GET(self) -> None:
            if not self._common_checks():
                return
            self.send_response(405)
            self.send_header("Allow", "POST")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self) -> None:
            if not self._common_checks():
                return
            accept = self.headers.get("Accept", "")
            if "application/json" not in accept or "text/event-stream" not in accept:
                self.send_error(406)
                return
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                self.send_error(415)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_error(400)
                return
            if length <= 0 or length > MAX_BODY:
                self.send_error(413 if length > MAX_BODY else 400)
                return
            try:
                raw = self.rfile.read(length)
                message = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                body = json.dumps(jsonrpc_error(None, -32700, "Parse error"), separators=(",", ":")).encode()
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if not isinstance(message, dict):
                status, response = 400, jsonrpc_error(None, -32600, "Invalid Request")
            else:
                status, response = dispatch_mcp(operator, message)
            if response is None:
                self.send_response(status)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = json.dumps(response, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def serve(operator: Any, *, host: str, port: int, token: str, allowed_origins: frozenset[str]) -> None:
    if not _is_loopback_host(host):
        raise TransportConfigError("Edge1 MCP transport must bind to loopback only")
    if not (1 <= port <= 65535):
        raise TransportConfigError("invalid TCP port")
    httpd = ThreadingHTTPServer((host, port), make_handler(operator, token, allowed_origins))
    httpd.serve_forever()


def main(build_operator: Callable[[], tuple[Any, Any]] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("EDGE1_OPERATOR_MCP_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("EDGE1_OPERATOR_MCP_PORT", str(DEFAULT_PORT))))
    args = parser.parse_args()
    if not _is_loopback_host(args.host):
        raise TransportConfigError("Edge1 MCP transport must bind to loopback only")
    token_file = Path(os.environ.get("EDGE1_OPERATOR_MCP_TOKEN_FILE", "/etc/edge1-operator/mcp-token"))
    token = load_bearer_token(token_file)
    origins = allowed_origins_from_env(os.environ.get("EDGE1_OPERATOR_ALLOWED_ORIGINS"))
    if build_operator is None:
        from .edge1_operator_entrypoint import build_operator as _build_operator
        build_operator = _build_operator
    operator, runtime = build_operator()
    runtime.health()
    serve(operator, host=args.host, port=args.port, token=token, allowed_origins=origins)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
