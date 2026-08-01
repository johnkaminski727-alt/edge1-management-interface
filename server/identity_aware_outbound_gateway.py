#!/usr/bin/env python3
"""Identity-aware facade for the outbound mail gateway core."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import mail_identity_registry
import outbound_mail_gateway


def status_payload(
    config: dict[str, Any],
    policy: dict[str, Any],
    identities: dict[str, Any],
) -> dict[str, Any]:
    status = outbound_mail_gateway.status_payload(config, policy)
    identity_status = mail_identity_registry.status_payload(identities)
    system_sender = identity_status["system_sender"]
    identity_status["identities"] = [
        item for item in identity_status["identities"]
        if item["address"] != system_sender
    ]
    status["sender_selection"] = identity_status
    return status


def prepare_payload(
    identities: dict[str, Any],
    payload: dict[str, Any],
) -> tuple[dict[str, Any], mail_identity_registry.SenderSelection]:
    if not isinstance(payload, dict):
        raise mail_identity_registry.IdentitySelectionError(
            "message payload must be an object"
        )
    hint = str(payload.get("identity_hint", "")).strip().casefold()
    system_sender = identities["sender_selection"]["system_sender"].casefold()
    system_profile_keys = {
        key.casefold()
        for key, profile in identities["sender_profiles"].items()
        if profile["address"].casefold() == system_sender
    }
    if hint and (hint == system_sender or hint in system_profile_keys):
        raise mail_identity_registry.IdentitySelectionError(
            "noreply identity requires system_generated=true"
        )

    selection = mail_identity_registry.resolve_sender(identities, payload)
    prepared = copy.deepcopy(payload)
    prepared["from_address"] = selection.address
    if selection.reply_to:
        prepared["reply_to"] = selection.reply_to
    else:
        prepared.pop("reply_to", None)
    return prepared, selection


def compose_preview(
    config: dict[str, Any],
    policy: dict[str, Any],
    identities: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    prepared, selection = prepare_payload(identities, payload)
    preview = outbound_mail_gateway.compose_preview(config, policy, prepared)
    preview["sender_selection"] = selection.to_dict()
    preview["request"]["sender_selection_reason"] = selection.reason
    preview["request"]["sender_identity_key"] = selection.identity_key
    preview["request"]["submitted_from_present"] = selection.submitted_from_present
    preview["request"]["from_address_replaced"] = selection.from_address_replaced
    preview["request"]["original_recipient"] = (
        str(payload.get("original_recipient", "")).strip().casefold() or None
    )
    preview["request"]["identity_hint"] = str(payload.get("identity_hint", "")).strip() or None
    preview["request"]["system_generated"] = payload.get("system_generated", False) is True
    return preview


def send_message(
    config: dict[str, Any],
    policy: dict[str, Any],
    identities: dict[str, Any],
    payload: dict[str, Any],
    *,
    confirmation: bool,
    audit_path: str | Path | None = None,
) -> dict[str, Any]:
    prepared, selection = prepare_payload(identities, payload)
    if not selection.live_enabled:
        raise outbound_mail_gateway.DeliveryDisabledError(
            "selected sender identity is not authorized for live delivery"
        )
    result = outbound_mail_gateway.send_message(
        config,
        policy,
        prepared,
        confirmation=confirmation,
        audit_path=None,
    )
    event = result["audit_event"]
    event["sender_address"] = selection.address
    event["sender_selection_reason"] = selection.reason
    event["sender_identity_key"] = selection.identity_key
    result["sender_selection"] = selection.to_dict()
    if audit_path is not None and policy["audit"]["write_jsonl"]:
        outbound_mail_gateway.append_audit_event(audit_path, event)
    return result
