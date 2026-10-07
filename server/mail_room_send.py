"""Signed client for the gateway send route, used only by the Mail Room server.

Kept separate from integrations.bigbird_mail, which stays prepare/read-only and
signs with the shared preparation secret. This client signs with
WWCX_MAIL_SEND_TOKEN as client "wwcx-mail-room"; the gateway accepts nothing
else on /outbound-mail/send.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

SEND_PATH = "/outbound-mail/send"
CLIENT_ID = "wwcx-mail-room"
SECRET_ENV = "WWCX_MAIL_SEND_TOKEN"


class MailSendError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class MailRoomSendClient:
    def __init__(self, *, secret: str, base_url: str = "http://127.0.0.1:8104", timeout_seconds: float = 90.0) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1", "localhost"} or parsed.port != 8104 or parsed.path not in {"", "/"}:
            raise ValueError("send client must target the loopback gateway on port 8104")
        if len(secret) < 32:
            raise ValueError("send secret must contain at least 32 characters")
        self.url = base_url.rstrip("/") + SEND_PATH
        self.secret = secret
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_environment(cls) -> "MailRoomSendClient | None":
        secret = os.getenv(SECRET_ENV, "")
        return cls(secret=secret) if len(secret) >= 32 else None

    def headers(self, body: bytes, *, timestamp: int | None = None, nonce: str | None = None) -> dict[str, str]:
        timestamp = int(time.time()) if timestamp is None else timestamp
        nonce = nonce or secrets.token_urlsafe(24)
        digest = hashlib.sha256(body).hexdigest()
        canonical = "\n".join(["WWCX-HMAC-SHA256", "POST", SEND_PATH, CLIENT_ID, str(timestamp), nonce, digest]).encode()
        return {
            "X-WWCX-Client-ID": CLIENT_ID,
            "X-WWCX-Timestamp": str(timestamp),
            "X-WWCX-Nonce": nonce,
            "X-WWCX-Content-SHA256": digest,
            "X-WWCX-Signature": hmac.new(self.secret.encode(), canonical, hashlib.sha256).hexdigest(),
            "Content-Type": "application/json",
        }

    def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("send payload must be an object")
        body = json.dumps({**payload, "confirm_send": True}, separators=(",", ":"), sort_keys=True).encode()
        request = urllib.request.Request(self.url, data=body, method="POST", headers=self.headers(body))
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw, status = response.read(), response.status
        except urllib.error.HTTPError as exc:
            raw, status = exc.read(), exc.code
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            # Outcome unknown: the gateway may have submitted before the connection dropped.
            raise MailSendError("outcome_unknown", "Gateway did not answer; check the Activity view before retrying.") from exc
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MailSendError("invalid_response") from exc
        if not 200 <= status < 300:
            raise MailSendError(str(decoded.get("error", "send_failed")), str(decoded.get("message", "")))
        return decoded
