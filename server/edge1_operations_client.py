"""Exact, server-side HMAC client for the loopback Edge1 Operations API."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ACTOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")
ACTION_PATHS = {
    "security.validate_config": "/v1/actions/security.validate_config/run",
}


class OperationsClientError(Exception):
    pass


class OperationsClientTimeout(OperationsClientError):
    pass


@dataclass(frozen=True)
class OperationsResult:
    event_id: str
    action_id: str
    status: str
    message: str
    duration_ms: int | None
    exit_code: int | None


class Edge1OperationsClient:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8097",
        secret_path: Path = Path("/etc/edge1-operations-api.secret"),
        timeout_seconds: int = 15,
        now: Any = time.time,
    ):
        if base_url != "http://127.0.0.1:8097":
            raise ValueError("Operations API origin must remain loopback and exact")
        if timeout_seconds < 1 or timeout_seconds > 60:
            raise ValueError("Operations API timeout is outside the accepted range")
        self.base_url = base_url
        self.secret_path = secret_path
        self.timeout_seconds = timeout_seconds
        self.now = now

    def _read_secret(self) -> bytes:
        try:
            if self.secret_path.is_symlink():
                raise OperationsClientError("Operations API secret path cannot be a symlink")
            mode = self.secret_path.stat().st_mode & 0o777
            if mode & 0o077:
                raise OperationsClientError("Operations API secret permissions are too broad")
            value = self.secret_path.read_bytes().strip()
        except OSError as exc:
            raise OperationsClientError("Operations API secret is unavailable") from exc
        if len(value) < 32:
            raise OperationsClientError("Operations API secret is invalid")
        return value

    def run(self, action_id: str, actor_subject: str) -> OperationsResult:
        path = ACTION_PATHS.get(action_id)
        if path is None:
            raise OperationsClientError("action is not allowlisted")
        actor = f"edge1-security-console:{actor_subject}"
        if not ACTOR_RE.fullmatch(actor):
            raise OperationsClientError("actor identity is invalid")
        body = b"{}"
        timestamp = str(int(self.now()))
        nonce = secrets.token_hex(24)
        body_hash = hashlib.sha256(body).hexdigest()
        canonical = "\n".join(("POST", path, timestamp, nonce, actor, body_hash)).encode("utf-8")
        signature = hmac.new(self._read_secret(), canonical, hashlib.sha256).hexdigest()
        request = Request(
            self.base_url + path,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-WWCX-Actor": actor,
                "X-WWCX-Nonce": nonce,
                "X-WWCX-Timestamp": timestamp,
                "X-WWCX-Signature": signature,
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                status_code = int(response.status)
                payload_bytes = response.read(65537)
        except HTTPError as exc:
            status_code = int(exc.code)
            payload_bytes = exc.read(65537)
        except TimeoutError as exc:
            raise OperationsClientTimeout("Operations API request timed out") from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise OperationsClientTimeout("Operations API request timed out") from exc
            raise OperationsClientError("Operations API is unavailable") from exc
        if len(payload_bytes) > 65536:
            raise OperationsClientError("Operations API response is too large")
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OperationsClientError("Operations API response is unreadable") from exc
        if not isinstance(payload, dict):
            raise OperationsClientError("Operations API response is invalid")
        event_id = payload.get("event_id")
        if not isinstance(event_id, str) or not EVENT_ID_RE.fullmatch(event_id):
            raise OperationsClientError("Operations API event identifier is missing")
        result_status = str(payload.get("status", "error"))
        if status_code == 200 and result_status == "succeeded":
            message = "The security configuration passed validation."
        elif status_code in (200, 409) and result_status in ("failed", "timed_out"):
            message = "The configuration needs attention. No running service settings were changed."
        elif status_code == 403:
            message = "The validation request was denied by the Operations API."
        else:
            message = "The validation request could not be completed."
        duration = payload.get("duration_ms")
        exit_code = payload.get("exit_code")
        return OperationsResult(
            event_id=event_id,
            action_id=action_id,
            status=result_status,
            message=message,
            duration_ms=duration if isinstance(duration, int) and duration >= 0 else None,
            exit_code=exit_code if isinstance(exit_code, int) else None,
        )
