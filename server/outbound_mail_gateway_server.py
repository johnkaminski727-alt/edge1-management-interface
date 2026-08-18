#!/usr/bin/env python3
"""Local admin API and static console for the WW.CX outbound-mail gateway."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
WEB_ROOT = REPO_ROOT / "src" / "web" / "outbound-mail"
DEFAULT_CONFIG = REPO_ROOT / "config" / "messaging" / "outbound-mail-gateway.json"
DEFAULT_IDENTITIES = REPO_ROOT / "config" / "messaging" / "mail-identities.json"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import identity_aware_outbound_gateway as identity_gateway
import mail_ai_adapter
import mail_identity_registry
import outbound_mail_gateway as gateway
import outbound_mail_policy
import outbound_mail_preparation_auth as preparation_auth


class GatewayApplication:
    def __init__(
        self,
        config_path: Path,
        identities_path: Path = DEFAULT_IDENTITIES,
        *,
        correspondence_db_path: Path | None = None,
        correspondence_enabled: bool | None = None,
    ) -> None:
        self.config_path = config_path.resolve()
        self.identities_path = identities_path.resolve()
        # These optional overrides are dependency injection for bounded local tests. The
        # production main() never supplies them, so runtime path policy remains enforced
        # by mail_ai_adapter's /var/lib/wwcx-mail-room constraint.
        self.correspondence_db_path = correspondence_db_path
        self.correspondence_enabled = correspondence_enabled

    def load(
        self,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path, Path]:
        config = gateway.load_json(self.config_path)
        gateway.validate_gateway_config(config)
        policy_path = gateway.resolve_repo_path(REPO_ROOT, config["paths"]["policy"])
        audit_path = gateway.resolve_repo_path(REPO_ROOT, config["paths"]["audit_jsonl"])
        nonce_path = gateway.resolve_repo_path(
            REPO_ROOT,
            config["preparation_api"]["nonce_store"],
        )
        policy = outbound_mail_policy.load_policy(policy_path)
        outbound_mail_policy.validate_policy(policy)
        identities = gateway.load_json(self.identities_path)
        mail_identity_registry.validate_registry(identities)
        return config, policy, identities, audit_path, nonce_path

    def correspondence_state(self) -> dict[str, Any]:
        return mail_ai_adapter.correspondence_read_state(
            db_path=self.correspondence_db_path,
            enabled=self.correspondence_enabled,
        )

    def correspondence_message(self, message_id: str) -> dict[str, Any]:
        return mail_ai_adapter.read_correspondence_message(
            message_id,
            db_path=self.correspondence_db_path,
            enabled=self.correspondence_enabled,
        )

    def correspondence_thread(self, thread_id: str) -> dict[str, Any]:
        return mail_ai_adapter.read_correspondence_thread(
            thread_id,
            limit=50,
            db_path=self.correspondence_db_path,
            enabled=self.correspondence_enabled,
        )


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "WWCXOutboundMailGateway/1.2"

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

    def _read_body(self, max_bytes: int) -> bytes:
        raw_length = self.headers.get("Content-Length", "")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise gateway.GatewayError("invalid Content-Length") from exc
        if length < 1 or length > max_bytes:
            raise gateway.GatewayError("request body length is invalid")
        return self.rfile.read(length)

    def _decode_json(self, body: bytes) -> dict[str, Any]:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise gateway.GatewayError("request body must be valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise gateway.GatewayError("request JSON must be an object")
        return payload

    def _read_json(self, max_bytes: int) -> dict[str, Any]:
        return self._decode_json(self._read_body(max_bytes))

    def _authenticate_preparation_api(
        self,
        config: dict[str, Any],
        nonce_path: Path,
        method: str,
        path: str,
        body: bytes,
    ) -> preparation_auth.VerifiedPreparationClient:
        return preparation_auth.verify_request(
            config["preparation_api"],
            dict(self.headers.items()),
            method,
            path,
            body,
            nonce_path,
        )

    def _handle_error(self, exc: Exception) -> None:
        if isinstance(exc, preparation_auth.PreparationApiDisabledError):
            status = HTTPStatus.FORBIDDEN
            code = "preparation_api_disabled"
        elif isinstance(exc, preparation_auth.PreparationAuthUnavailableError):
            status = HTTPStatus.SERVICE_UNAVAILABLE
            code = "preparation_auth_unavailable"
        elif isinstance(exc, preparation_auth.PreparationReplayError):
            status = HTTPStatus.CONFLICT
            code = "replay_detected"
        elif isinstance(exc, preparation_auth.InvalidPreparationAuthError):
            status = HTTPStatus.UNAUTHORIZED
            code = "authentication_failed"
            exc = RuntimeError("Preparation API authentication failed.")
        elif isinstance(exc, gateway.DeliveryDisabledError):
            status = HTTPStatus.FORBIDDEN
            code = "delivery_disabled"
        elif isinstance(exc, gateway.ProviderUnavailableError):
            status = HTTPStatus.SERVICE_UNAVAILABLE
            code = "provider_unavailable"
        elif isinstance(
            exc,
            (
                gateway.GatewayError,
                gateway.ConfigurationError,
                preparation_auth.PreparationAuthConfigurationError,
                mail_identity_registry.IdentityRegistryError,
                mail_ai_adapter.MailAIAdapterError,
                ValueError,
            ),
        ):
            status = HTTPStatus.BAD_REQUEST
            code = "invalid_request"
        else:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            code = "internal_error"
        self._send_json(status, {"error": code, "message": str(exc)})

    def _authenticated_get(
        self,
        config: dict[str, Any],
        nonce_path: Path,
        path: str,
    ) -> preparation_auth.VerifiedPreparationClient:
        return self._authenticate_preparation_api(config, nonce_path, "GET", path, b"")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            config, policy, identities, audit_path, nonce_path = self.application.load()
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
                self._send_json(
                    HTTPStatus.OK,
                    identity_gateway.status_payload(config, policy, identities),
                )
                return
            if parsed.path == "/outbound-mail/api/v1/status":
                client = self._authenticated_get(config, nonce_path, parsed.path)
                status_payload = identity_gateway.status_payload(config, policy, identities)
                status_payload["preparation_api"]["contract"] = (
                    "wwcx.outbound-mail-preparation-api.v1"
                )
                status_payload["preparation_api"]["authenticated_client_id"] = (
                    client.client_id
                )
                status_payload["correspondence_read"] = self.application.correspondence_state()
                self._send_json(HTTPStatus.OK, status_payload)
                return
            if parsed.path == "/outbound-mail/api/v1/correspondence/status":
                client = self._authenticated_get(config, nonce_path, parsed.path)
                payload = self.application.correspondence_state()
                payload["authenticated_client_id"] = client.client_id
                self._send_json(HTTPStatus.OK, payload)
                return

            message_prefix = "/outbound-mail/api/v1/correspondence/message/"
            if parsed.path.startswith(message_prefix):
                client = self._authenticated_get(config, nonce_path, parsed.path)
                encoded = parsed.path[len(message_prefix) :]
                if not encoded or "/" in encoded:
                    raise ValueError("correspondence message identifier is invalid")
                payload = self.application.correspondence_message(unquote(encoded))
                payload["authenticated_client_id"] = client.client_id
                self._send_json(HTTPStatus.OK, payload)
                return

            thread_prefix = "/outbound-mail/api/v1/correspondence/thread/"
            if parsed.path.startswith(thread_prefix):
                client = self._authenticated_get(config, nonce_path, parsed.path)
                encoded = parsed.path[len(thread_prefix) :]
                if not encoded or "/" in encoded:
                    raise ValueError("correspondence thread identifier is invalid")
                payload = self.application.correspondence_thread(unquote(encoded))
                payload["authenticated_client_id"] = client.client_id
                self._send_json(HTTPStatus.OK, payload)
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
            config, policy, identities, audit_path, nonce_path = self.application.load()
            if parsed.path == "/outbound-mail/api/v1/prepare":
                body = self._read_body(config["preparation_api"]["max_request_bytes"])
                client = self._authenticate_preparation_api(
                    config,
                    nonce_path,
                    "POST",
                    parsed.path,
                    body,
                )
                payload = self._decode_json(body)
                preview = identity_gateway.compose_preview(
                    config,
                    policy,
                    identities,
                    payload,
                )
                preview.pop("action_token", None)
                audit_event = dict(preview["audit_record"])
                audit_event.update(
                    {
                        "event": "outbound_message_prepared_api",
                        "occurred_at": datetime.now(timezone.utc).isoformat(
                            timespec="seconds"
                        ),
                        "client_id": client.client_id,
                        "sender_address": preview["request"]["from_address"],
                        "sender_selection_reason": preview["sender_selection"]["reason"],
                        "sender_identity_key": preview["sender_selection"]["identity_key"],
                        "delivery_status": "prepared_not_sent",
                    }
                )
                gateway.append_audit_event(audit_path, audit_event)
                preview["preparation_api"] = {
                    "contract": "wwcx.outbound-mail-preparation-api.v1",
                    "authenticated_client_id": client.client_id,
                    "delivery_status": "prepared_not_sent",
                }
                self._send_json(HTTPStatus.OK, preview)
                return

            max_bytes = config["admin"]["max_body_bytes"] + 65536
            payload = self._read_json(max_bytes)
            if parsed.path == "/outbound-mail/preview":
                preview = identity_gateway.compose_preview(config, policy, identities, payload)
                preview.pop("action_token", None)
                self._send_json(HTTPStatus.OK, preview)
                return
            if parsed.path == "/outbound-mail/send":
                confirmation = payload.pop("confirm_send", False) is True
                result = identity_gateway.send_message(
                    config,
                    policy,
                    identities,
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
    parser.add_argument("--identities", type=Path, default=DEFAULT_IDENTITIES)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    application = GatewayApplication(args.config, args.identities)
    config, policy, identities, _, _ = application.load()
    status = identity_gateway.status_payload(config, policy, identities)
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
                "automatic_sender_selection": status["sender_selection"][
                    "automatic_selection_enabled"
                ],
                "correspondence_read_enabled": application.correspondence_state()["read_enabled"],
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
