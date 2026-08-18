"""Authenticated Operations Center bridge for the loopback Edge1 SNMP API."""
from __future__ import annotations

import json
import secrets
from typing import Any

from .edge1_security_auth_core import AuthorizationError, GatewayError
from .edge1_security_auth_http_types import HttpRequest, HttpResponse
from .edge1_snmp_ui_client import MUTATING_POST_PATHS, SAFE_POST_PATHS, SnmpUiClientError, SnmpUiClientTimeout

SNMP_CONSOLE_PATH = "/edge1-ops/snmp/"
SNMP_API_PREFIX = "/edge1-ops/api/v1/snmp"
SNMP_READ_SCOPE = "edge1.security.read"
SNMP_OPERATE_SCOPE = "edge1.security.validate"

_BROWSER_POST_FIELDS = {
    "/api/snmp/ai/query": frozenset({"question", "use_model"}),
    "/api/snmp/ai/incidents": frozenset({"minutes"}),
    "/api/snmp/devices": frozenset({
        "display_name", "hostname", "management_address", "device_type", "vendor", "model",
        "serial_number", "site", "location", "tags", "owner", "environment", "snmp_version",
        "credential_reference", "polling_enabled", "polling_interval", "trap_enabled", "timezone", "metadata",
    }),
    "/api/snmp/discovery": frozenset({"cidr", "credential_reference", "dry_run", "concurrency"}),
    "/api/snmp/mibs/import": frozenset({"module"}),
    "/api/snmp/alerts/evaluate": frozenset(),
    "/api/snmp/actions": frozenset({"action", "target", "reason", "ai_involvement"}),
}


def normalize_snmp_browser_payload(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on browser POST fields that could widen the approved trust boundary."""
    allowed = _BROWSER_POST_FIELDS.get(path)
    if allowed is None:
        raise ValueError("snmp_browser_operation_not_allowed")
    unexpected = set(payload) - allowed
    if unexpected:
        raise ValueError("snmp_browser_payload_fields_invalid")
    result = dict(payload)
    if path in {"/api/snmp/devices", "/api/snmp/discovery"}:
        # The normal Operations Console is intentionally SNMPv3-only. A separately
        # approved non-browser caller may use the backend's explicit legacy gate.
        if "legacy_protocol_approved" in payload:
            raise ValueError("snmp_legacy_browser_approval_forbidden")
        if path == "/api/snmp/devices" and str(result.get("snmp_version", "3")) != "3":
            raise ValueError("snmp_browser_requires_v3")
    if path == "/api/snmp/discovery":
        concurrency = result.get("concurrency", 16)
        if isinstance(concurrency, bool) or not isinstance(concurrency, int) or not 1 <= concurrency <= 64:
            raise ValueError("snmp_discovery_concurrency_invalid")
        result["concurrency"] = concurrency
        result["dry_run"] = bool(result.get("dry_run", True))
    if path == "/api/snmp/ai/incidents":
        minutes = result.get("minutes", 60)
        if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= 10080:
            raise ValueError("snmp_incident_window_invalid")
        result["minutes"] = minutes
    if path == "/api/snmp/actions":
        if result.get("ai_involvement", False) is not False:
            raise ValueError("snmp_browser_ai_attribution_invalid")
        result["ai_involvement"] = False
    return result


class SecuritySnmpHttpMixin:
    """Adds SNMP console and allowlisted API proxying to the existing Edge1 session boundary."""

    def _snmp_console(self, request: HttpRequest) -> HttpResponse:
        token = self._session_token(request)
        context = self.gateway.authenticate_session(token, self._request_id())
        if SNMP_READ_SCOPE not in context.scopes:
            raise AuthorizationError("console_scope_required")
        if not self.gateway.store.allow_rate(
            "snmp-console:" + context.session_identifier_hash,
            int(self.now()),
            limit=self.config.session_requests,
            window_seconds=self.config.session_window_seconds,
        ):
            return self._json(429, {"error": "rate_limited"})
        path = self.snmp_console_path
        if path is None or path.is_symlink() or not path.is_file():
            raise GatewayError("snmp_console_unavailable")
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise GatewayError("snmp_console_unavailable") from exc
        if source.count("<style>") != 1 or source.count("<script>") != 1:
            raise GatewayError("snmp_console_template_invalid")
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

    def _snmp_api(self, request: HttpRequest) -> HttpResponse:
        token = self._session_token(request)
        context = self.gateway.authenticate_session(token, self._request_id())
        if SNMP_READ_SCOPE not in context.scopes:
            raise AuthorizationError("console_scope_required")
        upstream = self._snmp_upstream_path(request.path)
        method = request.method.upper()
        payload: dict[str, Any] | None = None
        rate_kind = "snmp-read"
        rate_limit = self.config.session_requests
        rate_window = self.config.session_window_seconds
        if method == "POST":
            self._require_same_origin(request)
            self._require_csrf(request, context.session_identifier_hash)
            if self._content_type(request) != "application/json":
                raise ValueError("content_type_invalid")
            try:
                decoded = json.loads(request.body.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("json_invalid") from exc
            if not isinstance(decoded, dict):
                raise ValueError("json_object_required")
            base_path = upstream.split("?", 1)[0]
            payload = normalize_snmp_browser_payload(base_path, decoded)
            if base_path in MUTATING_POST_PATHS:
                if SNMP_OPERATE_SCOPE not in context.scopes:
                    raise AuthorizationError("snmp_operate_scope_required")
                rate_kind = "snmp-mutate"
                rate_limit = self.config.action_requests
                rate_window = self.config.action_window_seconds
            elif base_path in SAFE_POST_PATHS:
                rate_kind = "snmp-ai"
                rate_limit = self.config.action_requests
                rate_window = self.config.action_window_seconds
        if not self.gateway.store.allow_rate(
            rate_kind + ":" + context.session_identifier_hash,
            int(self.now()),
            limit=rate_limit,
            window_seconds=rate_window,
        ):
            return self._json(429, {"error": "rate_limited"})
        try:
            status, result = self.snmp.request(method, upstream, actor_subject=context.subject, payload=payload)
        except SnmpUiClientTimeout:
            return self._json(503, {"error": "snmp_api_timeout"})
        except SnmpUiClientError:
            return self._json(503, {"error": "snmp_api_unavailable"})
        return self._json(status, result if isinstance(result, dict) else {"result": result})

    @staticmethod
    def _snmp_upstream_path(path: str) -> str:
        if not path.startswith(SNMP_API_PREFIX):
            raise ValueError("snmp_path_invalid")
        suffix = path[len(SNMP_API_PREFIX):]
        if suffix and not suffix.startswith(("/", "?")):
            raise ValueError("snmp_path_invalid")
        return "/api/snmp" + suffix
