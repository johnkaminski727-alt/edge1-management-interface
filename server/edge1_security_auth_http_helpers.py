"""Cookie, CSRF, header, and response helpers for the Edge1 Security HTTP adapter."""
from __future__ import annotations

import json
import secrets
from typing import Any, Mapping

from .edge1_security_auth_core import AuthenticationError, AuthorizationError, hash_secret
from .edge1_security_auth_http_types import COOKIE_VALUE_RE, HttpRequest, HttpResponse


class SecurityHttpHelpersMixin:
    def _require_same_origin(self, request: HttpRequest) -> None:
        if self._header(request, "origin") != self.config.same_origin:
            raise AuthorizationError("origin_invalid")

    def _require_csrf(self, request: HttpRequest, session_hash: str) -> None:
        token = self._header(request, "x-wwcx-csrf")
        if not COOKIE_VALUE_RE.fullmatch(token):
            raise AuthorizationError("csrf_invalid")
        if not self.gateway.store.verify_csrf(session_hash, hash_secret(token), int(self.now())):
            raise AuthorizationError("csrf_invalid")

    def _session_token(self, request: HttpRequest) -> str:
        cookies = self._cookies(request)
        token = cookies.get(self.config.session_cookie_name, "")
        if not COOKIE_VALUE_RE.fullmatch(token):
            raise AuthenticationError("session_missing")
        return token

    def _cookies(self, request: HttpRequest) -> dict[str, str]:
        raw = self._header(request, "cookie")
        result: dict[str, str] = {}
        if not raw:
            return result
        for item in raw.split(";"):
            if "=" not in item:
                raise ValueError("cookie_invalid")
            name, value = item.strip().split("=", 1)
            if not name or name in result:
                raise ValueError("cookie_invalid")
            result[name] = value
        return result

    def _request_id(self) -> str:
        return "edge1-http-" + secrets.token_hex(16)

    def _header(self, request: HttpRequest, name: str) -> str:
        target = name.lower()
        for key, value in request.headers.items():
            if key.lower() == target:
                return str(value).strip()
        return ""

    def _content_type(self, request: HttpRequest) -> str:
        return self._header(request, "content-type").split(";", 1)[0].strip().lower()

    def _session_cookie(self, token: str) -> str:
        return (
            f"{self.config.session_cookie_name}={token}; Path={self.config.cookie_path}; "
            "Secure; HttpOnly; SameSite=Strict"
        )

    def _csrf_cookie(self, token: str) -> str:
        return (
            f"{self.config.csrf_cookie_name}={token}; Path={self.config.cookie_path}; "
            "Secure; SameSite=Strict"
        )

    def _clear_cookie(self, name: str, *, http_only: bool) -> str:
        suffix = "; HttpOnly" if http_only else ""
        return (
            f"{name}=; Path={self.config.cookie_path}; Max-Age=0; "
            f"Secure{suffix}; SameSite=Strict"
        )

    def _base_headers(self) -> tuple[tuple[str, str], ...]:
        return (
            ("Cache-Control", "no-store, max-age=0"),
            ("Pragma", "no-cache"),
            ("Referrer-Policy", "no-referrer"),
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"),
        )

    def _json(self, status: int, payload: Mapping[str, Any]) -> HttpResponse:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return HttpResponse(
            status,
            self._base_headers() + (
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ),
            body,
        )
