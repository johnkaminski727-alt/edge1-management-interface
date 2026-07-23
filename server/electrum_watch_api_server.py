#!/usr/bin/env python3
"""Local read-only API wrapper for the Edge1 Electrum watch-only wallet."""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_RPC_ENV = Path("/etc/electrum-watch/rpc.env")
DEFAULT_API_ENV = Path("/etc/electrum-watch/api.env")
MAX_RESPONSE_BYTES = 1024 * 1024
ALLOWED_METHODS = {
    "/v1/wallet/info": "getinfo",
    "/v1/wallet/balance": "getbalance",
}


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def electrum_rpc(method: str) -> object:
    config = load_env(Path(os.environ.get("ELECTRUM_RPC_ENV", str(DEFAULT_RPC_ENV))))
    host = config.get("ELECTRUM_RPC_HOST", "")
    port = config.get("ELECTRUM_RPC_PORT", "")
    user = config.get("ELECTRUM_RPC_USER", "")
    password = config.get("ELECTRUM_RPC_PASSWORD", "")
    if host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Electrum RPC must be loopback-only")
    if not port.isdigit() or not user or not password:
        raise RuntimeError("Electrum RPC configuration is incomplete")

    credentials = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        f"http://{host}:{port}",
        data=json.dumps({"jsonrpc": "2.0", "id": "wwcx-api", "method": method, "params": []}).encode("utf-8"),
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError("Electrum RPC response exceeded limit")
    payload = json.loads(body.decode("utf-8"))
    if payload.get("error"):
        raise RuntimeError("Electrum RPC returned an error")
    if "result" not in payload:
        raise RuntimeError("Electrum RPC response omitted result")
    return payload["result"]


def sanitized_wallet_state() -> dict[str, object]:
    result = electrum_rpc("list_wallets")
    wallets = result if isinstance(result, list) else []
    synchronized = bool(wallets) and all(
        isinstance(wallet, dict) and wallet.get("synchronized") is True
        for wallet in wallets
    )
    return {
        "loaded": bool(wallets),
        "count": len(wallets),
        "synchronized": synchronized,
    }


def expected_token() -> str:
    config = load_env(Path(os.environ.get("ELECTRUM_API_ENV", str(DEFAULT_API_ENV))))
    token = config.get("ELECTRUM_API_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError("API token is missing or too short")
    return token


class Handler(BaseHTTPRequestHandler):
    server_version = "Edge1ElectrumWatchAPI/1.2"

    def send_json(self, status: HTTPStatus, payload: object) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        supplied = header.removeprefix("Bearer ").strip()
        try:
            supplied_bytes = supplied.encode("utf-8")
            expected_bytes = expected_token().encode("utf-8")
        except UnicodeError:
            return False
        return secrets.compare_digest(supplied_bytes, expected_bytes)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/healthz":
            self.send_json(HTTPStatus.OK, {"status": "ok", "service": "electrum-watch-api"})
            return
        if path not in ALLOWED_METHODS and path != "/v1/wallet/state":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            if not self.authorized():
                self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            result = sanitized_wallet_state() if path == "/v1/wallet/state" else electrum_rpc(ALLOWED_METHODS[path])
            self.send_json(HTTPStatus.OK, {"ok": True, "result": result})
        except (OSError, ValueError, RuntimeError, urllib.error.URLError):
            self.send_json(HTTPStatus.BAD_GATEWAY, {"error": "backend_unavailable"})

    def do_POST(self) -> None:  # noqa: N802
        self.send_json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "read_only"})

    def log_message(self, format: str, *args: object) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8094)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Electrum watch API must bind to loopback")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
