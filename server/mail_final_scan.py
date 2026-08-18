#!/usr/bin/env python3
"""Fail-closed final outbound MIME scan contract for WW.CX Mail Room.

This module is provider-neutral and performs no scanning or network activity itself.
A trusted server-side scanner adapter receives the exact serialized MIME bytes that
would be submitted to a provider and must return a normalized result. Missing,
malformed, incomplete, or non-clean results block provider submission.
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable


CONTRACT = "wwcx.mail-final-scan.v1"
NORMALIZED_STATES = {
    "clean",
    "infected",
    "suspicious",
    "unscannable",
    "scan_error",
    "not_scanned",
}


class FinalScanError(RuntimeError):
    """Raised when final outbound MIME cannot be proven clean."""


def _require_text(value: Any, label: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FinalScanError(f"{label} must be non-empty text")
    normalized = value.strip()
    if "\r" in normalized or "\n" in normalized or len(normalized) > maximum:
        raise FinalScanError(f"{label} is invalid")
    return normalized


def normalize_result(result: Any, message_bytes: bytes) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise FinalScanError("final scanner must return an object")
    expected = {
        "contract",
        "state",
        "engine",
        "engine_version",
        "ruleset_version",
        "message_sha256",
        "reason_codes",
    }
    if set(result) != expected:
        raise FinalScanError("final scan result keys are invalid")
    if result["contract"] != CONTRACT:
        raise FinalScanError("unsupported final scan contract")
    state = _require_text(result["state"], "state").casefold()
    if state not in NORMALIZED_STATES:
        raise FinalScanError("final scan state is unsupported")
    engine = _require_text(result["engine"], "engine")
    engine_version = _require_text(result["engine_version"], "engine_version")
    ruleset_version = _require_text(result["ruleset_version"], "ruleset_version")
    expected_sha256 = hashlib.sha256(message_bytes).hexdigest()
    if result["message_sha256"] != expected_sha256:
        raise FinalScanError("final scan digest does not match composed MIME")
    reason_codes = result["reason_codes"]
    if not isinstance(reason_codes, list) or any(
        not isinstance(item, str) or not item.strip() or len(item) > 128
        for item in reason_codes
    ):
        raise FinalScanError("reason_codes must be a list of bounded strings")
    if len(reason_codes) > 64 or len(set(reason_codes)) != len(reason_codes):
        raise FinalScanError("reason_codes are invalid")
    return {
        "contract": CONTRACT,
        "state": state,
        "engine": engine,
        "engine_version": engine_version,
        "ruleset_version": ruleset_version,
        "message_sha256": expected_sha256,
        "reason_codes": list(reason_codes),
    }


def require_clean(
    message_bytes: bytes,
    scanner: Callable[[bytes], dict[str, Any]] | None,
) -> dict[str, Any]:
    if not isinstance(message_bytes, bytes) or not message_bytes:
        raise FinalScanError("final composed MIME bytes are required")
    if scanner is None or not callable(scanner):
        raise FinalScanError("final outbound scanner is not configured")
    result = normalize_result(scanner(message_bytes), message_bytes)
    if result["state"] != "clean":
        raise FinalScanError(f"final outbound scan is not clean: {result['state']}")
    return result
