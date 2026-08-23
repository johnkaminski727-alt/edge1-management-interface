#!/usr/bin/env python3
"""Loopback client for the hardened Edge1 Operations API.

The MCP-facing operator never accepts arbitrary commands, URLs, ports, paths,
or action names. Runtime code calls this client only with a fixed allowlist.
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
from pathlib import Path
from urllib.parse import quote, urlparse


DEFAULT_BASE_URL = os.environ.get("EDGE1_OPS_URL", "http://127.0.0.1:8097")
DEFAULT_SECRET_FILE = Path(
    os.environ.get("EDGE1_OPS_SECRET_FILE", "/etc/edge1-operations-api.secret")
)
DEFAULT_ACTOR = os.environ.get("EDGE1_OPERATOR_ACTOR", "edge1-operator-mcp")


class OperationsClientError(RuntimeError):
    """Raised when a bounded Operations API call cannot be completed safely."""


class Edge1OperationsClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        secret_file: Path = DEFAULT_SECRET_FILE,
        actor: str = DEFAULT_ACTOR,
        timeout: float = 30.0,
        allowed_actions: set[str] | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}:
            raise ValueError("Operations API must use loopback HTTP")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Operations API URL must not embed credentials or parameters")
        self.base_url = base_url.rstrip("/")
        self.secret_file = Path(secret_file)
        self.actor = actor.strip()
        self.timeout = timeout
        self.allowed_actions = frozenset(allowed_actions or ())
        if not self.actor:
            raise ValueError("operator actor must not be empty")

    def _read_secret(self) -> bytes:
        secret = self.secret_file.read_bytes().strip()
        if len(secret) < 32:
            raise OperationsClientError("Operations API secret is unavailable or too short")
        return secret

    def _decode_response(self, response) -> dict:
        raw = response.read()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OperationsClientError("Operations API returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise OperationsClientError("Operations API returned a non-object response")
        return payload

    def _request(self, method: str, path: str, body: bytes = b"", authenticated: bool = True) -> dict:
        headers = {"Accept": "application/json"}
        if body:
            headers["Content-Type"] = "application/json"
        if authenticated:
            timestamp = str(int(time.time()))
            nonce = secrets.token_hex(16)
            body_hash = hashlib.sha256(body).hexdigest()
            canonical = "\n".join(
                (method, path, timestamp, nonce, self.actor, body_hash)
            ).encode("utf-8")
            signature = hmac.new(self._read_secret(), canonical, hashlib.sha256).hexdigest()
            headers.update(
                {
                    "X-WWCX-Actor": self.actor,
                    "X-WWCX-Nonce": nonce,
                    "X-WWCX-Timestamp": timestamp,
                    "X-WWCX-Signature": signature,
                }
            )
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body if method != "GET" else None,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return self._decode_response(response)
        except urllib.error.HTTPError as exc:
            detail = f"HTTP {exc.code}"
            try:
                payload = json.loads(exc.read().decode("utf-8"))
                if isinstance(payload, dict) and isinstance(payload.get("error"), str):
                    detail = payload["error"]
            except Exception:
                pass
            raise OperationsClientError(f"Operations API request failed: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise OperationsClientError("Operations API is unavailable") from exc

    def health(self) -> dict:
        return self._request("GET", "/healthz", authenticated=False)

    def list_actions(self) -> dict:
        return self._request("GET", "/v1/actions")

    def run_action(self, action_name: str, parameters: dict | None = None) -> dict:
        if action_name not in self.allowed_actions:
            raise OperationsClientError("action is not exposed by the Edge1 Operator")
        path = f"/v1/actions/{quote(action_name, safe='')}/run"
        body = json.dumps(parameters or {}, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return self._request("POST", path, body=body)
