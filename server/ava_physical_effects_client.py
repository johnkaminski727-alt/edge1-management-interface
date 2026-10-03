#!/usr/bin/env python3
"""Unprivileged client for AVA's local physical-effects broker.

This module contains no hardware executor. It can submit only a request ID and
a fixed catalogue identifier to the local Unix-domain broker. The broker remains
authoritative for enablement, dedupe, rate limiting, persistence and execution.
"""

from __future__ import annotations

import json
import math
import socket
from typing import Any

try:
    from ava_physical_effects_protocol import MAX_REQUEST_BYTES, PROTOCOL_VERSION
except ImportError:
    from server.ava_physical_effects_protocol import MAX_REQUEST_BYTES, PROTOCOL_VERSION


DEFAULT_SOCKET_PATH = "/run/ava-physical-effects/control.sock"
DEFAULT_TIMEOUT_SECONDS = 0.5

_ALLOWED_DISPOSITIONS = frozenset({
    "disabled",
    "approved",
    "duplicate",
    "rate_limited",
})


class PhysicalEffectsClientError(RuntimeError):
    """Raised when broker submission or response validation fails closed."""


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PhysicalEffectsClientError("duplicate response field")
        result[key] = value
    return result


def _request_payload(request_id: str, catalogue_effect: str) -> bytes:
    if not isinstance(request_id, str) or not request_id:
        raise PhysicalEffectsClientError("invalid request_id")
    if not isinstance(catalogue_effect, str) or not catalogue_effect:
        raise PhysicalEffectsClientError("invalid catalogue_effect")

    payload = json.dumps(
        {
            "version": PROTOCOL_VERSION,
            "request_id": request_id,
            "catalogue_effect": catalogue_effect,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"

    if len(payload) > MAX_REQUEST_BYTES:
        raise PhysicalEffectsClientError("request exceeds protocol limit")

    return payload


def _read_response(connection: socket.socket) -> bytes:
    data = bytearray()

    while len(data) <= MAX_REQUEST_BYTES:
        chunk = connection.recv(
            min(256, MAX_REQUEST_BYTES + 1 - len(data))
        )
        if not chunk:
            break
        data.extend(chunk)
        if b"\n" in chunk:
            break

    if not data:
        raise PhysicalEffectsClientError("broker returned no response")
    if len(data) > MAX_REQUEST_BYTES:
        raise PhysicalEffectsClientError("broker response too large")
    if not data.endswith(b"\n"):
        raise PhysicalEffectsClientError("broker response missing newline")

    body = bytes(data[:-1])
    if b"\n" in body:
        raise PhysicalEffectsClientError("broker returned multiple responses")

    return body


def _validate_response(
    raw: bytes,
    request_id: str,
    catalogue_effect: str,
) -> dict[str, Any]:
    try:
        response = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except PhysicalEffectsClientError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PhysicalEffectsClientError("invalid broker response") from exc

    if not isinstance(response, dict):
        raise PhysicalEffectsClientError("broker response must be an object")

    if set(response) != {
        "version",
        "request_id",
        "catalogue_effect",
        "disposition",
    }:
        raise PhysicalEffectsClientError("broker response fields are not exact")

    if (
        type(response["version"]) is not int
        or response["version"] != PROTOCOL_VERSION
    ):
        raise PhysicalEffectsClientError("broker protocol version mismatch")

    if response["request_id"] != request_id:
        raise PhysicalEffectsClientError("broker request_id mismatch")

    if response["catalogue_effect"] != catalogue_effect:
        raise PhysicalEffectsClientError("broker catalogue_effect mismatch")

    disposition = response["disposition"]
    if (
        not isinstance(disposition, str)
        or disposition not in _ALLOWED_DISPOSITIONS
    ):
        raise PhysicalEffectsClientError("broker disposition is not approved")

    return response


def submit(
    request_id: str,
    catalogue_effect: str,
    *,
    socket_path: str = DEFAULT_SOCKET_PATH,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    payload = _request_payload(request_id, catalogue_effect)

    if not isinstance(socket_path, str) or not socket_path.startswith("/"):
        raise PhysicalEffectsClientError("invalid broker socket path")

    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
        or timeout > 2.0
    ):
        raise PhysicalEffectsClientError("invalid broker timeout")

    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    try:
        connection.settimeout(float(timeout))
        connection.connect(socket_path)
        connection.sendall(payload)
        raw = _read_response(connection)
    except (OSError, socket.timeout) as exc:
        raise PhysicalEffectsClientError(
            "physical effects broker unavailable"
        ) from exc
    finally:
        connection.close()

    return _validate_response(raw, request_id, catalogue_effect)
