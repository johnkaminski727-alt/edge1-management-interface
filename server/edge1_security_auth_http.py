"""Denied-by-default request adapter for Business159 assertions and Edge1 sessions."""
from __future__ import annotations

import dataclasses
import hashlib
import secrets
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlsplit

from .edge1_operations_client import Edge1OperationsClient
from .edge1_security_auth_core import AuthenticationError, AuthorizationError, GatewayError, hash_secret, valid_event_id
from .edge1_security_auth_gateway import Edge1SecurityAuthGateway
from .edge1_security_auth_http_actions import SecurityHttpActionMixin
from .edge1_security_auth_http_config import HttpAdapterConfig
from .edge1_security_auth_http_helpers import SecurityHttpHelpersMixin
from .edge1_security_auth_http_snmp import SNMP_API_PREFIX, SNMP_CONSOLE_PATH, SecuritySnmpHttpMixin
from .edge1_security_auth_http_types import LOOPBACKS, HttpRequest, HttpResponse
from .edge1_snmp_ui_client import Edge1SnmpUiClient

CONSOLE_READ_SCOPE = "edge1.security.read"

# Short-lived host-only interactive return state. The cookie remains as a
# backward-compatible fallback, while the WW.CX bridge also carries the same
# bounded destination identifier explicitly across the assertion handoff.
# Neither mechanism accepts an arbitrary URL.
INTERACTIVE_LOGIN_URL = "https://ww.cx/admin/edge1-security-login.php"
INTERACTIVE_DESTINATION_FIELD = "edge1_destination"
INTERACTIVE_RETURN_COOKIE_NAME = "__Secure-wwcx_edge1_ops_return"
INTERACTIVE_RETURN_COOKIE_PATH = "/edge1-ops/session/exchange"
INTERACTIVE_RETURN_MAX_AGE = 900


class Edge1SecurityAuthHttpAdapter(SecuritySnmpHttpMixin, SecurityHttpActionMixin, SecurityHttpHelpersMixin):
    def __init__(
        self,
        config: HttpAdapterConfig,
        gateway: Edge1SecurityAuthGateway,
        operations: Optional[Edge1OperationsClient] = None,
        snmp: Optional[Edge1SnmpUiClient] = None,
        *,
        console_path: Optional[Path] = None,
        snmp_console_path: Optional[Path] = None,
        now: Any = time.time,
    ):
        self.config = config
        self.gateway = gateway
        self.operations = operations or Edge1OperationsClient(
            base_url=config.operations_origin,
            secret_path=config.operations_secret_path,
            timeout_seconds=config.operations_timeout_seconds,
            now=now,
        )
        self.snmp = snmp or Edge1SnmpUiClient(now=now)
        self.console_path = console_path
        self.snmp_console_path = snmp_console_path
        self.now = now

    def handle(self, request: HttpRequest) -> HttpResponse:
        try:
            self._validate_boundary(request)
            route = self.config.routes
            parsed = urlsplit(request.path)
            if request.path == route["health"]:
                return self._method(request, {"GET"}, self._health)
            if not self.config.live_route_authorized:
                raise GatewayError("live_route_not_authorized")
            if request.path == route["console"]:
                return self._method(request, {"GET"}, self._console)
            if request.path == SNMP_CONSOLE_PATH:
                return self._method(request, {"GET"}, self._snmp_console)
            if parsed.path == SNMP_API_PREFIX or parsed.path.startswith(SNMP_API_PREFIX + "/"):
                return self._method(request, {"GET", "POST"}, self._snmp_api)
            if request.path == route["exchange"]:
                return self._method(request, {"POST"}, self._exchange)
            if request.path == route["session"]:
                return self._method(request, {"GET"}, self._session)
            if request.path == route["logout"]:
                return self._method(request, {"POST"}, self._logout)
            if request.path == route["validate"]:
                return self._method(request, {"POST"}, self._validate_action)
            return self._json(404, {"error": "not_found"})
        except ValueError:
            return self._json(400, {"error": "bad_request"})
        except AuthenticationError:
            if request.method.upper() == "GET":
                if request.path == self.config.routes["console"]:
                    return self._interactive_login_redirect("security")
                if request.path == SNMP_CONSOLE_PATH:
                    return self._interactive_login_redirect("snmp")
            return self._json(401, {"error": "authentication_required"})
        except AuthorizationError:
            return self._json(403, {"error": "forbidden"})
        except GatewayError:
            return self._json(503, {"error": "authentication_service_unavailable"})
        except Exception:
            return self._json(503, {"error": "service_unavailable"})

    def _interactive_return_cookie(self, token: str) -> str:
        if token not in {"security", "snmp"}:
            raise ValueError("interactive_return_invalid")
        return (
            f"{INTERACTIVE_RETURN_COOKIE_NAME}={token}; "
            f"Path={INTERACTIVE_RETURN_COOKIE_PATH}; "
            f"Max-Age={INTERACTIVE_RETURN_MAX_AGE}; "
            "Secure; HttpOnly; SameSite=Strict"
        )

    def _clear_interactive_return_cookie(self) -> str:
        return (
            f"{INTERACTIVE_RETURN_COOKIE_NAME}=; "
            f"Path={INTERACTIVE_RETURN_COOKIE_PATH}; "
            "Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; "
            "Secure; HttpOnly; SameSite=Strict"
        )

    def _interactive_login_redirect(self, token: str) -> HttpResponse:
        if token not in {"security", "snmp"}:
            raise ValueError("interactive_return_invalid")
        return HttpResponse(
            302,
            self._base_headers() + (
                ("Location", f"{INTERACTIVE_LOGIN_URL}?{INTERACTIVE_DESTINATION_FIELD}={token}"),
                ("Set-Cookie", self._interactive_return_cookie(token)),
                ("Content-Length", "0"),
            ),
            b"",
        )

    def _interactive_return_target(self, token: str) -> str:
        if token == "snmp":
            return SNMP_CONSOLE_PATH
        if token == "security":
            return self.config.routes["console"]
        return self.config.routes["redirect_after_exchange"]

    def _validate_boundary(self, request: HttpRequest) -> None:
        if not self.config.enabled or not self.config.deployment_authorized:
            raise GatewayError("http_adapter_disabled")
        if request.remote_addr not in LOOPBACKS:
            raise AuthorizationError("non_loopback_backend_client")
        if request.scheme != "https" or request.host != self.config.allowed_host:
            raise AuthorizationError("untrusted_proxy_boundary")
        if len(request.body) > self.config.maximum_body_bytes:
            raise ValueError("body_too_large")
        parsed = urlsplit(request.path)
        if parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path.startswith("/"):
            raise ValueError("path_invalid")
        if parsed.query and not (
            parsed.path == SNMP_API_PREFIX or parsed.path.startswith(SNMP_API_PREFIX + "/")
        ):
            raise ValueError("path_invalid")

    def _method(self, request: HttpRequest, allowed: set[str], handler: Any) -> HttpResponse:
        if request.method.upper() not in allowed:
            response = self._json(405, {"error": "method_not_allowed"})
            return dataclasses.replace(
                response,
                headers=response.headers + (("Allow", ", ".join(sorted(allowed))),),
            )
        return handler(request)

    def _health(self, request: HttpRequest) -> HttpResponse:
        return self._json(200, {
            "status": "ok",
            "live_route_authorized": self.config.live_route_authorized,
            "mutations_enabled": False,
            "snmp_console_enabled": self.snmp_console_path is not None,
        })

    def _console(self, request: HttpRequest) -> HttpResponse:
        token = self._session_token(request)
        context = self.gateway.authenticate_session(token, self._request_id())
        if CONSOLE_READ_SCOPE not in context.scopes:
            raise AuthorizationError("console_scope_required")
        if not self.gateway.store.allow_rate(
            "console:" + context.session_identifier_hash,
            int(self.now()),
            limit=self.config.session_requests,
            window_seconds=self.config.session_window_seconds,
        ):
            return self._json(429, {"error": "rate_limited"})
        path = self.console_path
        if path is None or path.is_symlink() or not path.is_file():
            raise GatewayError("console_unavailable")
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise GatewayError("console_unavailable") from exc
        if source.count("<style>") != 1 or source.count("<script>") != 1:
            raise GatewayError("console_template_invalid")
        nonce = secrets.token_urlsafe(24)
        rendered = source.replace("<style>", f'<style nonce="{nonce}">', 1)
        rendered = rendered.replace("<script>", f'<script nonce="{nonce}">', 1)
        body = rendered.encode("utf-8")
        headers = (
            ("Cache-Control", "no-store, max-age=0"),
            ("Pragma", "no-cache"),
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Referrer-Policy", "no-referrer"),
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()"),
            ("Cross-Origin-Opener-Policy", "same-origin"),
            ("Cross-Origin-Resource-Policy", "same-origin"),
            (
                "Content-Security-Policy",
                "default-src 'self'; "
                f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            ),
        )
        return HttpResponse(200, headers, body)

    def _exchange_origin_allowed(self, request: HttpRequest) -> bool:
        origin = self._header(request, "origin")
        if origin == self.config.business159_origin:
            return True
        if origin != "null":
            return False
        return (
            self._header(request, "sec-fetch-site").lower() == "same-site"
            and self._header(request, "sec-fetch-mode").lower() == "navigate"
            and self._header(request, "sec-fetch-dest").lower() == "document"
        )

    def _exchange(self, request: HttpRequest) -> HttpResponse:
        if not self._exchange_origin_allowed(request):
            raise AuthorizationError("origin_invalid")
        if self._content_type(request) != "application/x-www-form-urlencoded":
            raise ValueError("content_type_invalid")
        remote_key = hashlib.sha256(("exchange\x00" + request.remote_addr).encode("utf-8")).hexdigest()
        if not self.gateway.store.allow_rate(
            "exchange:" + remote_key,
            int(self.now()),
            limit=self.config.exchange_requests,
            window_seconds=self.config.exchange_window_seconds,
        ):
            return self._json(429, {"error": "rate_limited"})
        try:
            form_text = request.body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("form_encoding_invalid") from exc
        form = parse_qs(form_text, strict_parsing=True, max_num_fields=5)
        required_fields = {"assertion", "request_id"}
        optional_fields = {INTERACTIVE_DESTINATION_FIELD}
        if (
            not required_fields.issubset(form)
            or set(form) - required_fields - optional_fields
            or any(len(values) != 1 for values in form.values())
        ):
            raise ValueError("form_invalid")
        assertion = form["assertion"][0]
        request_id = form["request_id"][0]
        if not valid_event_id(request_id):
            raise ValueError("request_id_invalid")
        explicit_destination = form.get(INTERACTIVE_DESTINATION_FIELD, [""])[0]
        if explicit_destination and explicit_destination not in {"snmp", "security"}:
            raise ValueError("interactive_destination_invalid")
        return_cookie = self._cookies(request).get(INTERACTIVE_RETURN_COOKIE_NAME, "")
        selected_destination = explicit_destination or return_cookie
        redirect_target = self._interactive_return_target(selected_destination)
        destination_marker = selected_destination if selected_destination in {"snmp", "security"} else "fallback"
        session_token, context = self.gateway.exchange_assertion(assertion, request_id)
        csrf_token = secrets.token_urlsafe(32)
        self.gateway.store.set_csrf(
            context.session_identifier_hash,
            hash_secret(csrf_token),
            context.expires_at,
        )
        headers = self._base_headers() + (
            ("Location", redirect_target),
            ("X-WWCX-Interactive-Destination", destination_marker),
            ("Set-Cookie", self._session_cookie(session_token)),
            ("Set-Cookie", self._csrf_cookie(csrf_token)),
        )
        if return_cookie:
            headers += (("Set-Cookie", self._clear_interactive_return_cookie()),)
        return HttpResponse(303, headers, b"")

    def _session(self, request: HttpRequest) -> HttpResponse:
        token = self._session_token(request)
        context = self.gateway.authenticate_session(token, self._request_id())
        if CONSOLE_READ_SCOPE not in context.scopes:
            raise AuthorizationError("console_scope_required")
        if not self.gateway.store.allow_rate(
            "session:" + context.session_identifier_hash,
            int(self.now()),
            limit=self.config.session_requests,
            window_seconds=self.config.session_window_seconds,
        ):
            return self._json(429, {"error": "rate_limited"})
        return self._json(200, {
            "authenticated": True,
            "display_name": context.display_name,
            "source_role": context.source_role,
            "scopes": sorted(context.scopes),
            "expires_at": context.expires_at,
            "authentication_event_id": context.authentication_event_id,
        })

    def _logout(self, request: HttpRequest) -> HttpResponse:
        self._require_same_origin(request)
        token = self._session_token(request)
        context = self.gateway.authenticate_session(token, self._request_id())
        if not self.gateway.store.allow_rate(
            "logout:" + context.session_identifier_hash,
            int(self.now()),
            limit=self.config.logout_requests,
            window_seconds=self.config.logout_window_seconds,
        ):
            return self._json(429, {"error": "rate_limited"})
        self._require_csrf(request, context.session_identifier_hash)
        self.gateway.logout(token, self._request_id())
        return HttpResponse(
            204,
            self._base_headers() + (
                ("Set-Cookie", self._clear_cookie(self.config.session_cookie_name, http_only=True)),
                ("Set-Cookie", self._clear_cookie(self.config.csrf_cookie_name, http_only=False)),
            ),
            b"",
        )


__all__ = [
    "Edge1SecurityAuthHttpAdapter",
    "HttpAdapterConfig",
    "HttpRequest",
    "HttpResponse",
]
