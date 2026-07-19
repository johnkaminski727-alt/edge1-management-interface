from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class MessagingGatewayError(RuntimeError):
    """Raised when the internal messaging management API cannot be used safely."""


@dataclass(frozen=True)
class MessagingGatewayClient:
    base_url: str
    read_token: str
    control_token: str | None = None
    timeout_seconds: float = 5.0

    def status(self) -> dict[str, Any]:
        return self._request("GET", "/v1/management/status", token=self.read_token)

    def pause(self, *, actor: str, reason: str) -> dict[str, Any]:
        return self._control("pause", actor=actor, reason=reason)

    def resume(self, *, actor: str, reason: str) -> dict[str, Any]:
        return self._control("resume", actor=actor, reason=reason)

    def _control(self, action: str, *, actor: str, reason: str) -> dict[str, Any]:
        if not self.control_token:
            raise MessagingGatewayError("messaging control credential is not configured")
        if not actor.strip() or not reason.strip():
            raise ValueError("actor and reason are required for messaging control actions")
        return self._request(
            "POST",
            "/v1/management/control",
            token=self.control_token,
            payload={"action": action, "actor": actor, "reason": reason},
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            f"{self.base_url.rstrip('/')}{path}",
            data=data,
            method=method,
            headers={
                "accept": "application/json",
                "content-type": "application/json",
                "authorization": f"Bearer {token}",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise MessagingGatewayError(
                f"messaging gateway returned HTTP {exc.code}: {detail[:300]}"
            ) from exc
        except URLError as exc:
            raise MessagingGatewayError(f"messaging gateway unavailable: {exc.reason}") from exc

        try:
            result = json.loads(body)
        except json.JSONDecodeError as exc:
            raise MessagingGatewayError("messaging gateway returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise MessagingGatewayError("messaging gateway returned an invalid response shape")
        return result
