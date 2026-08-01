#!/usr/bin/env python3
"""HMAC authentication and replay protection for preparation-only mail API clients."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


AUTHENTICATION = "hmac_sha256"
CLIENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,63}$")
NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,80}$")

HEADER_CLIENT_ID = "X-WWCX-Client-ID"
HEADER_TIMESTAMP = "X-WWCX-Timestamp"
HEADER_NONCE = "X-WWCX-Nonce"
HEADER_CONTENT_SHA256 = "X-WWCX-Content-SHA256"
HEADER_SIGNATURE = "X-WWCX-Signature"


class PreparationAuthError(RuntimeError):
    """Base class for authenticated preparation API failures."""


class PreparationAuthConfigurationError(PreparationAuthError):
    """Raised when the preparation API policy is malformed."""


class PreparationApiDisabledError(PreparationAuthError):
    """Raised when an external preparation client reaches a closed gate."""


class PreparationAuthUnavailableError(PreparationAuthError):
    """Raised when runtime authentication material is unavailable."""


class InvalidPreparationAuthError(PreparationAuthError):
    """Raised when authentication metadata or signatures are invalid."""


class PreparationReplayError(PreparationAuthError):
    """Raised when a client reuses a nonce within the replay window."""


@dataclass(frozen=True)
class VerifiedPreparationClient:
    client_id: str
    timestamp: int
    nonce: str
    content_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "content_sha256": self.content_sha256,
        }


def _require_exact_keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise PreparationAuthConfigurationError(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        raise PreparationAuthConfigurationError(
            f"{label} keys invalid; missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )


def _require_int(value: Any, label: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or not minimum <= value <= maximum:
        raise PreparationAuthConfigurationError(
            f"{label} must be between {minimum} and {maximum}"
        )
    return value


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PreparationAuthConfigurationError(f"{label} must be non-empty text")
    return value.strip()


def validate_config(config: dict[str, Any]) -> None:
    _require_exact_keys(
        config,
        {
            "enabled",
            "authentication",
            "secret_env",
            "allowed_clients",
            "clock_skew_seconds",
            "nonce_ttl_seconds",
            "nonce_store",
            "max_request_bytes",
        },
        "preparation_api",
    )
    if not isinstance(config["enabled"], bool):
        raise PreparationAuthConfigurationError("preparation_api.enabled must be boolean")
    if config["authentication"] != AUTHENTICATION:
        raise PreparationAuthConfigurationError("unsupported preparation API authentication")
    secret_env = _require_text(config["secret_env"], "preparation_api.secret_env")
    if not ENV_NAME_RE.fullmatch(secret_env):
        raise PreparationAuthConfigurationError("preparation_api.secret_env is invalid")
    clients = config["allowed_clients"]
    if not isinstance(clients, list) or not clients or len(clients) > 50:
        raise PreparationAuthConfigurationError(
            "preparation_api.allowed_clients must contain between 1 and 50 clients"
        )
    if any(not isinstance(item, str) or not CLIENT_RE.fullmatch(item) for item in clients):
        raise PreparationAuthConfigurationError("preparation_api.allowed_clients is invalid")
    if len(set(clients)) != len(clients):
        raise PreparationAuthConfigurationError("preparation_api.allowed_clients must be unique")
    skew = _require_int(
        config["clock_skew_seconds"],
        "preparation_api.clock_skew_seconds",
        30,
        900,
    )
    ttl = _require_int(
        config["nonce_ttl_seconds"],
        "preparation_api.nonce_ttl_seconds",
        60,
        86400,
    )
    if ttl < skew:
        raise PreparationAuthConfigurationError(
            "preparation_api.nonce_ttl_seconds must not be shorter than clock skew"
        )
    _require_text(config["nonce_store"], "preparation_api.nonce_store")
    _require_int(
        config["max_request_bytes"],
        "preparation_api.max_request_bytes",
        1024,
        10 * 1024 * 1024,
    )


def status_payload(
    config: dict[str, Any],
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    validate_config(config)
    source = os.environ if environment is None else environment
    secret = str(source.get(config["secret_env"], ""))
    return {
        "enabled": config["enabled"],
        "authentication": config["authentication"],
        "runtime_secret_configured": len(secret) >= 32,
        "allowed_client_count": len(config["allowed_clients"]),
        "clock_skew_seconds": config["clock_skew_seconds"],
        "replay_protection": "sqlite_nonce_store",
    }


def content_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical_request(
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


def build_headers(
    secret: str,
    client_id: str,
    method: str,
    path: str,
    body: bytes,
    *,
    timestamp: int | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    if len(secret) < 32:
        raise ValueError("preparation API secret must contain at least 32 characters")
    if not CLIENT_RE.fullmatch(client_id):
        raise ValueError("preparation API client ID is invalid")
    resolved_timestamp = int(time.time()) if timestamp is None else int(timestamp)
    resolved_nonce = secrets.token_urlsafe(24) if nonce is None else nonce
    if not NONCE_RE.fullmatch(resolved_nonce):
        raise ValueError("preparation API nonce is invalid")
    digest = content_sha256(body)
    signature = hmac.new(
        secret.encode("utf-8"),
        canonical_request(
            method,
            path,
            client_id,
            resolved_timestamp,
            resolved_nonce,
            digest,
        ),
        hashlib.sha256,
    ).hexdigest()
    return {
        HEADER_CLIENT_ID: client_id,
        HEADER_TIMESTAMP: str(resolved_timestamp),
        HEADER_NONCE: resolved_nonce,
        HEADER_CONTENT_SHA256: digest,
        HEADER_SIGNATURE: signature,
    }


def _normalized_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {str(key).casefold(): str(value).strip() for key, value in headers.items()}


def _required_header(headers: Mapping[str, str], name: str) -> str:
    value = headers.get(name.casefold(), "")
    if not value:
        raise InvalidPreparationAuthError("required preparation API header is missing")
    return value


def _claim_nonce(
    nonce_store: Path,
    client_id: str,
    nonce: str,
    now: int,
    ttl_seconds: int,
) -> None:
    nonce_store.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(nonce_store), timeout=5)
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS used_nonces ("
            "client_id TEXT NOT NULL, nonce TEXT NOT NULL, used_at INTEGER NOT NULL, "
            "PRIMARY KEY(client_id, nonce))"
        )
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM used_nonces WHERE used_at < ?", (now - ttl_seconds,))
        try:
            connection.execute(
                "INSERT INTO used_nonces(client_id,nonce,used_at) VALUES(?,?,?)",
                (client_id, nonce, now),
            )
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise PreparationReplayError("preparation API nonce was already used") from exc
        connection.commit()
    finally:
        connection.close()
    try:
        os.chmod(nonce_store, 0o600)
    except OSError:
        pass


def verify_request(
    config: dict[str, Any],
    headers: Mapping[str, str],
    method: str,
    path: str,
    body: bytes,
    nonce_store: str | Path,
    *,
    now: int | None = None,
    environment: Mapping[str, str] | None = None,
) -> VerifiedPreparationClient:
    validate_config(config)
    if not config["enabled"]:
        raise PreparationApiDisabledError("external preparation API is disabled")
    if len(body) > config["max_request_bytes"]:
        raise InvalidPreparationAuthError("preparation API request exceeds size limit")

    normalized = _normalized_headers(headers)
    client_id = _required_header(normalized, HEADER_CLIENT_ID)
    if client_id not in config["allowed_clients"]:
        raise InvalidPreparationAuthError("preparation API client is not allowed")
    timestamp_text = _required_header(normalized, HEADER_TIMESTAMP)
    try:
        timestamp = int(timestamp_text)
    except ValueError as exc:
        raise InvalidPreparationAuthError("preparation API timestamp is invalid") from exc
    resolved_now = int(time.time()) if now is None else int(now)
    if abs(resolved_now - timestamp) > config["clock_skew_seconds"]:
        raise InvalidPreparationAuthError("preparation API timestamp is outside the allowed window")

    nonce = _required_header(normalized, HEADER_NONCE)
    if not NONCE_RE.fullmatch(nonce):
        raise InvalidPreparationAuthError("preparation API nonce is invalid")
    supplied_digest = _required_header(normalized, HEADER_CONTENT_SHA256).casefold()
    if not HEX_SHA256_RE.fullmatch(supplied_digest):
        raise InvalidPreparationAuthError("preparation API content digest is invalid")
    actual_digest = content_sha256(body)
    if not hmac.compare_digest(supplied_digest, actual_digest):
        raise InvalidPreparationAuthError("preparation API content digest does not match")

    supplied_signature = _required_header(normalized, HEADER_SIGNATURE).casefold()
    if not HEX_SHA256_RE.fullmatch(supplied_signature):
        raise InvalidPreparationAuthError("preparation API signature is invalid")
    source = os.environ if environment is None else environment
    secret = str(source.get(config["secret_env"], ""))
    if len(secret) < 32:
        raise PreparationAuthUnavailableError(
            "preparation API runtime secret is not configured"
        )
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        canonical_request(
            method,
            path,
            client_id,
            timestamp,
            nonce,
            actual_digest,
        ),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise InvalidPreparationAuthError("preparation API signature was not accepted")

    _claim_nonce(
        Path(nonce_store),
        client_id,
        nonce,
        resolved_now,
        config["nonce_ttl_seconds"],
    )
    return VerifiedPreparationClient(
        client_id=client_id,
        timestamp=timestamp,
        nonce=nonce,
        content_sha256=actual_digest,
    )
