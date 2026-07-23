#!/usr/bin/env python3
"""Deterministic, local-only messaging simulation.

No network, carrier, modem, SMPP, SIP MESSAGE, SMS, or MMS interfaces are used.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

RECIPIENT_PATTERN = re.compile(r"^\+[1-9][0-9]{7,14}$")
MAX_BODY_LENGTH = 1600


def simulate_message(payload: dict[str, Any]) -> dict[str, Any]:
    recipient = str(payload.get("recipient", "")).strip()
    body = str(payload.get("body", ""))
    sender_label = str(payload.get("sender_label", "WW.CX Sandbox")).strip()

    errors: list[str] = []
    if not RECIPIENT_PATTERN.fullmatch(recipient):
        errors.append("recipient must be an E.164-formatted synthetic test number")
    if not body:
        errors.append("body is required")
    if len(body) > MAX_BODY_LENGTH:
        errors.append(f"body exceeds {MAX_BODY_LENGTH} characters")
    if not sender_label:
        errors.append("sender_label is required")

    if errors:
        return {
            "mode": "sandbox",
            "accepted": False,
            "status": "validation_failed",
            "errors": errors,
            "external_delivery_attempted": False,
            "production_actions_enabled": False,
        }

    digest = hashlib.sha256(
        f"{sender_label}\n{recipient}\n{body}".encode("utf-8")
    ).hexdigest()[:20]

    return {
        "mode": "sandbox",
        "accepted": True,
        "message_id": f"sim-{digest}",
        "status": "simulated_only",
        "recipient": recipient,
        "sender_label": sender_label,
        "body_length": len(body),
        "simulated_at": datetime.now(timezone.utc).isoformat(),
        "stages": ["validated", "queued_in_memory", "gateway_path_simulated", "delivery_suppressed"],
        "external_delivery_attempted": False,
        "production_actions_enabled": False,
    }
