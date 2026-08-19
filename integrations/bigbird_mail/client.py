from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import quote, urlparse


class MailGatewayError(RuntimeError):
    pass


class MailGatewayClient:
    """Authenticated loopback client for bounded Mail Room status/read/draft operations."""

    def __init__(
        self,
        *,
        base_url: str,
        secret: str,
        client_id: str = "wwcx-private-ai",
        timeout_seconds: float = 5.0,
    ) -> None:
        self.base_url = self._validate_base_url(base_url)
        self.secret = str(secret)
        self.client_id = str(client_id).strip()
        self.timeout_seconds = float(timeout_seconds)
        if len(self.secret) < 32:
            raise ValueError("mail gateway secret must contain at least 32 characters")
        if not self.client_id or len(self.client_id) > 64:
            raise ValueError("mail gateway client ID is invalid")
        if not 0.1 <= self.timeout_seconds <= 30.0:
            raise ValueError("mail gateway timeout is invalid")

    @staticmethod
    def _validate_base_url(value: str) -> str:
        parsed = urlparse(str(value).strip())
        if parsed.scheme != "http":
            raise ValueError("mail gateway must use the approved loopback HTTP scheme")
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("mail gateway must be loopback-only")
        if parsed.port not in {None, 8104}:
            raise ValueError("mail gateway port is not approved")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("mail gateway base URL is invalid")
        if parsed.path not in {"", "/"}:
            raise ValueError("mail gateway base URL must not include a path")
        return str(value).strip().rstrip("/")

    @staticmethod
    def _canonical_request(
        method: str,
        path: str,
        client_id: str,
        timestamp: int,
        nonce: str,
        body_sha256: str,
    ) -> bytes:
        return "\n".join(
            [
                "WWCX-HMAC-SHA256",
                method.upper(),
                path,
                client_id,
                str(timestamp),
                nonce,
                body_sha256,
            ]
        ).encode("utf-8")

    def _headers(self, method: str, path: str, body: bytes) -> dict[str, str]:
        timestamp = int(time.time())
        nonce = secrets.token_urlsafe(24)
        digest = hashlib.sha256(body).hexdigest()
        signature = hmac.new(
            self.secret.encode("utf-8"),
            self._canonical_request(
                method,
                path,
                self.client_id,
                timestamp,
                nonce,
                digest,
            ),
            hashlib.sha256,
        ).hexdigest()
        return {
            "X-WWCX-Client-ID": self.client_id,
            "X-WWCX-Timestamp": str(timestamp),
            "X-WWCX-Nonce": nonce,
            "X-WWCX-Content-SHA256": digest,
            "X-WWCX-Signature": signature,
        }

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not path.startswith("/outbound-mail/api/v1/"):
            raise ValueError("mail client path is outside the approved API")
        body = b""
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        headers = self._headers(method, path, body)
        if body:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path,
            data=body if method != "GET" else None,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
                status = int(response.status)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = int(exc.code)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise MailGatewayError("mail gateway request failed") from exc
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MailGatewayError("mail gateway returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise MailGatewayError("mail gateway returned an invalid response")
        if status < 200 or status >= 300:
            code = str(decoded.get("error", "request_failed"))
            raise MailGatewayError(f"mail gateway rejected request: {code}")
        return decoded

    def status(self) -> dict[str, Any]:
        return self._request("GET", "/outbound-mail/api/v1/status")

    def correspondence_status(self) -> dict[str, Any]:
        return self._request("GET", "/outbound-mail/api/v1/correspondence/status")

    def correspondence_message(self, message_id: str) -> dict[str, Any]:
        canonical = str(message_id).strip()
        if not canonical:
            raise ValueError("message_id is required")
        encoded = quote(canonical, safe="")
        return self._request(
            "GET",
            f"/outbound-mail/api/v1/correspondence/message/{encoded}",
        )

    def correspondence_thread(self, thread_id: str) -> dict[str, Any]:
        canonical = str(thread_id).strip()
        if not canonical:
            raise ValueError("thread_id is required")
        encoded = quote(canonical, safe="")
        return self._request(
            "GET",
            f"/outbound-mail/api/v1/correspondence/thread/{encoded}",
        )

    def prepare_draft(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise ValueError("draft request must be an object")
        return self._request("POST", "/outbound-mail/api/v1/prepare", request)
