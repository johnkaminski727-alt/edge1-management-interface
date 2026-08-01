#!/usr/bin/env python3
"""Local admin API and static console for the WW.CX outbound-mail gateway."""

from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
WEB_ROOT = REPO_ROOT / "src" / "web" / "outbound-mail"
DEFAULT_CONFIG = REPO_ROOT / "config" / "messaging" / "outbound-mail-gateway.json"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import outbound_mail_gateway as gateway
import outbound_mail_policy


class GatewayApplication:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path.resolve()

    def load(self) -> tuple[dict[str, Any], dict[str, Any], Path]:
        config = gateway.load_json(self.config_path)
        gateway.validate_gateway_config(config)
        policy_path = gateway.resolve_repo_path(REPO_ROOT, config["paths"]["policy"])
        audit_path = gateway.resolve_repo_path(REPO_ROOT, config["paths"]["audit_jsonl"])
        policy = outbound_mail_policy.load_policy(policy_path)
        outbound_mail_policy.validate_policy(policy)
        return config, policy, audit_path


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "WWCXOutboundMailGateway/1.0"

    @property
    def application(self) -> GatewayApplication:
        return self.server.application  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write(
            "%s - - [%s] %s\n"
            % (self.address_string(), self.log_date_time_string(), format % args)
        )

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'",
        )

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _serve_asset(self, path: Path, content_type: str) -> None:
        if not path.is_file() or WEB_ROOT.resolve() not in path.resolve().parents:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "asset_not_found"})
            return
        self._send_bytes(HTTPStatus.OK, path.read_bytes(), content_type)

    def _read_json(self, max_bytes: int) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise gateway.GatewayError("invalid Content-Length") from exc
        if length < 1 or length > max_bytes:
            raise gateway.GatewayError("request body length is invalid")
        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise gateway.GatewayError("request body must be valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise gateway.GatewayError("request JSON must be an object")
        return payload

    def _handle_error(self, exc: Exception) -> None:
        if isinstance(exc, gateway.DeliveryDisabledError):
            status = HTTPStatus.FORBIDDEN
            code = "delivery_disabled"
        elif isinstance(exc, gateway.ProviderUnavailableError):
            status = HTTPStatus.SERVICE_UNAVAILABLE
            code = "provider_unavailable"
        elif isinstance(exc, (gateway.GatewayError, gateway.ConfigurationError, ValueError)):
            status = HTTPStatus.BAD_REQUEST
            code = "invalid_request"
        else:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            code = "internal_error"
        self._send_json(status, {"error": code, "message": str(exc)})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            config, policy, audit_path = self.application.load()
            if parsed.path in {"/outbound-mail", "/outbound-mail/"}:
                self._serve_asset(WEB_ROOT / "index.html", "text/html; charset=utf-8")
                return
            if parsed.path == "/outbound-mail/app.js":
                self._serve_asset(WEB_ROOT / "app.js", "text/javascript; charset=utf-8")
                return
            if parsed.path == "/outbound-mail/styles.css":
                self._serve_asset(WEB_ROOT / "styles.css", "text/css; charset=utf-8")
                return
            if parsed.path == "/outbound-mail/healthz":
                self._send_json(
                    HTTPStatus.OK,
                    {"status": "ok", "gateway": "wwcx-outbound-mail-gateway"},
                )
                return
            if parsed.path == "/outbound-mail/status":
                self._send_json(HTTPStatus.OK, gateway.status_payload(config, policy))
                return
            if parsed.path == "/outbound-mail/audit":
                query = parse_qs(parsed.query)
                raw_limit = query.get("limit", ["50"])[0]
                try:
                    limit = int(raw_limit)
                except ValueError:
                    limit = 50
                limit = min(max(limit, 1), config["admin"]["audit_view_limit"])
                events = gateway.read_audit_events(audit_path, limit)
                self._send_json(
                    HTTPStatus.OK,
                    {"events": events, "count": len(events), "limit": limit},
                )
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except Exception as exc:
            self._handle_error(exc)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            config, policy, audit_path = self.application.load()
            max_bytes = config["admin"]["max_body_bytes"] + 65536
            payload = self._read_json(max_bytes)
            if parsed.path == "/outbound-mail/preview":
                preview = gateway.compose_preview(config, policy, payload)
                preview.pop("action_token", None)
                self._send_json(HTTPStatus.OK, preview)
                return
            if parsed.path == "/outbound-mail/send":
                confirmation = payload.pop("confirm_send", False) is True
                result = gateway.send_message(
                    config,
                    policy,
                    payload,
                    confirmation=confirmation,
                    audit_path=audit_path,
                )
                self._send_json(HTTPStatus.ACCEPTED, result)
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except Exception as exc:
            self._handle_error(exc)


class GatewayServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], application: GatewayApplication) -> None:
        super().__init__(address, GatewayHandler)
        self.application = application


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    application = GatewayApplication(args.config)
    config, policy, _ = application.load()
    status = gateway.status_payload(config, policy)
    host = args.host or config["listen"]["host"]
    port = args.port or config["listen"]["port"]
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("Refusing non-loopback bind; use an authenticated reverse proxy")
    print(
        json.dumps(
            {
                "event": "outbound_mail_gateway_start",
                "host": host,
                "port": port,
                "external_delivery_enabled": status["external_delivery_enabled"],
            },
            sort_keys=True,
        )
    )
    server = GatewayServer((host, port), application)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
