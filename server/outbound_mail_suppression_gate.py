#!/usr/bin/env python3
"""Fail-closed pre-send suppression checks for the outbound-mail gateway.

The module hashes normalized recipient addresses, reads minimized suppression
state, and refuses submission before a provider callable is invoked. It does
not inspect credentials, expose a listener, modify suppression state, or send
mail by itself.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

import outbound_mail_delivery_events as delivery_events
import outbound_mail_gateway as gateway


class SuppressionGateError(gateway.DeliveryDisabledError):
    """Base class for suppression-gate delivery refusal."""


class SuppressionStateUnavailableError(SuppressionGateError):
    """Raised when required suppression state is unavailable."""


class SuppressedRecipientError(SuppressionGateError):
    """Raised when one or more hashed recipients are actively suppressed."""

    def __init__(self, suppressed: list[dict[str, Any]]) -> None:
        self.suppressed = suppressed
        reasons = sorted(
            {
                str(item.get("suppression_reason") or "unknown")
                for item in suppressed
            }
        )
        super().__init__(
            "delivery refused because recipient suppression is active "
            f"for {len(suppressed)} recipient(s); reasons={reasons}"
        )


def recipient_sha256(address: str) -> str:
    normalized = address.strip().casefold()
    if not normalized or "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise gateway.GatewayError("recipient address is invalid for suppression lookup")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def suppression_preflight(
    database: str | Path,
    recipients: list[str],
    *,
    required: bool = True,
) -> dict[str, Any]:
    path = Path(database)
    hashes = [recipient_sha256(item) for item in recipients]
    if len(hashes) != len(set(hashes)):
        raise gateway.GatewayError("recipient list contains duplicates after normalization")
    if not path.is_file():
        if required:
            raise SuppressionStateUnavailableError(
                "delivery refused because suppression state is unavailable"
            )
        return {
            "checked": False,
            "required": False,
            "database_present": False,
            "recipient_count": len(hashes),
            "suppressed_recipient_count": 0,
            "recipient_hashes": hashes,
        }
    suppressed = delivery_events.suppressed_recipients(path, hashes)
    if suppressed:
        raise SuppressedRecipientError(suppressed)
    return {
        "checked": True,
        "required": required,
        "database_present": True,
        "recipient_count": len(hashes),
        "suppressed_recipient_count": 0,
        "recipient_hashes": hashes,
    }


def guarded_identity_send(
    send_callable: Callable[..., dict[str, Any]],
    config: dict[str, Any],
    policy: dict[str, Any],
    identities: dict[str, Any],
    payload: dict[str, Any],
    *,
    confirmation: bool,
    audit_path: str | Path,
    suppression_database: str | Path,
) -> dict[str, Any]:
    request = gateway.normalize_message_request(config, payload)
    preflight = suppression_preflight(
        suppression_database,
        list(request["recipients"]),
        required=True,
    )
    result = send_callable(
        config,
        policy,
        identities,
        payload,
        confirmation=confirmation,
        audit_path=audit_path,
    )
    if not isinstance(result, dict):
        raise gateway.GatewayError("guarded send callable returned an invalid result")
    output = dict(result)
    output["suppression_preflight"] = {
        "checked": preflight["checked"],
        "recipient_count": preflight["recipient_count"],
        "suppressed_recipient_count": 0,
    }
    return output
