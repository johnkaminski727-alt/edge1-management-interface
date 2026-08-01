#!/usr/bin/env python3
"""Loopback-only administrative and ingestion API for the WW.CX inbound mail hub."""

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
DEFAULT_CONFIG = REPO_ROOT / "config" / "messaging" / "inbound-mail-hub.json"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import inbound_mail_hub as hub


class HubApplication:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path.resolve()

    def load(self) -> tuple[dict[str, Any], Path, Path]:
        config = hub.load_json(self.config_path)
        hub.validate_config(config)
        audit_path = self._repo_path(config["paths"]["audit_jsonl"])
        quarantine_path = self._repo_path(config["paths"]["quarantine_jsonl"])
        return config, audit_path, quarantine_path

    @staticmethod
    def _repo_path(configured: str) -> Path:
        root = REPO_ROOT.resolve()
        candidate = (root / configured).resolve()
        if root != candidate and root not in candidate.parents:
            raise hub.ConfigurationError("configured path escapes repository root")
        return candidate


class HubHandler(BaseHTTPRequestHandler):
    server_version = "WWCXInboundMailHub/1.0"

    @property
    def application(self) -> HubApplication:
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
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self, max_bytes: int) -> dict[str, Any]:
        raw = self.headers.get("Content-Length", "")
        try:
            length = int(raw)
        except ValueError as exc:
            raise hub.InboundHubError("invalid Content-Length") from exc
        if length < 1 or length > max_bytes:
            raise hub.InboundHubError("request body length is invalid")
        data = self.rfile.read(length)
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise hub.InboundHubError("request body must be valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise hub.InboundHubError("request JSON must be an object")
        return payload

    def _handle_error(self, exc: Exception) -> None:
        if isinstance(exc, hub.AuthenticationError):
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "authentication_failed", "message": str(exc)})
        elif isinstance(exc, hub.IngressDisabledError):
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "routing_disabled", "message": str(exc)})
        elif isinstance(exc, (hub.InboundHubError, hub.ConfigurationError, ValueError)):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request", "message": str(exc)})
        else:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            config, audit_path, quarantine_path = self.application.load()
            if parsed.path == "/mail-hub/healthz":
                self._send_json(HTTPStatus.OK, {"status": "ok", "hub": "wwcx-inbound-mail-hub"})
                return
            if parsed.path == "/mail-hub/status":
                self._send_json(HTTPStatus.OK, hub.status_payload(config))
                return
            if parsed.path in {"/mail-hub/audit", "/mail-hub/quarantine"}:
                query = parse_qs(parsed.query)
                try:
                    limit = int(query.get("limit", ["50"])[0])
                except ValueError:
                    limit = 50
                limit = min(max(limit, 1), config["limits"]["audit_view_limit"])
                path = audit_path if parsed.path.endswith("audit") else quarantine_path
                events = hub.read_events(path, limit)
                self._send_json(HTTPStatus.OK, {"events": events, "count": len(events), "limit": limit})
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except Exception as exc:
            self._handle_error(exc)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            config, audit_path, quarantine_path = self.application.load()
            if parsed.path != "/mail-hub/ingest":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            payload = self._read_json(config["limits"]["max_message_bytes"] + 65536)
            token = self.headers.get("X-WWCX-Inbound-Token")
            result = hub.process_ingress(config, payload, token)
            hub.append_jsonl(audit_path, result["event"])
            quarantined = [
                item for item in result["event"]["decisions"]
                if item["action"] == "quarantine"
            ]
            if quarantined:
                hub.append_jsonl(
                    quarantine_path,
                    {
                        "event": "inbound_message_quarantined",
                        "occurred_at": result["event"]["occurred_at"],
                        "provider_message_id_sha256": result["event"]["provider_message_id_sha256"],
                        "decisions": quarantined,
                        "contract": hub.CONTRACT,
                    },
                )
            self._send_json(HTTPStatus.ACCEPTED, result)
        except Exception as exc:
            self._handle_error(exc)


class HubServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], application: HubApplication) -> None:
        super().__init__(address, HubHandler)
        self.application = application


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    application = HubApplication(args.config)
    config, _, _ = application.load()
    host = args.host or config["listen"]["host"]
    port = args.port or config["listen"]["port"]
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("Refusing non-loopback bind; use an authenticated reverse proxy")
    print(json.dumps({"event": "inbound_mail_hub_start", "host": host, "port": port, "state": hub.status_payload(config)["state"]}, sort_keys=True))
    server = HubServer((host, port), application)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
