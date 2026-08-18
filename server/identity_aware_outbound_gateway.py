#!/usr/bin/env python3
"""Identity-aware facade for the outbound mail gateway core."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

import mail_identity_registry
import mail_secure_submission
import mail_threading
import outbound_mail_gateway


CATCH_ALL_PROPOSAL_REASON = "original_recipient_catch_all_proposal"


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


def _normalized_original_recipient(payload: dict[str, Any]) -> str | None:
    value = payload.get("original_recipient")
    if value is None or str(value).strip() == "":
        return None
    try:
        return mail_identity_registry.normalize_address(value, "original_recipient")
    except mail_identity_registry.IdentityConfigurationError as exc:
        raise mail_identity_registry.IdentitySelectionError(str(exc)) from exc


def _resolve_sender_with_catchall_proposal(
    identities: dict[str, Any],
    payload: dict[str, Any],
) -> mail_identity_registry.SenderSelection:
    """Resolve a registered sender or safely propose an unseen managed-domain recipient.

    Catch-all inbound routing means the exact original envelope recipient may not yet be
    present in the outbound identity registry. For preparation only, an unseen address
    at a managed domain is temporarily added to a copy of the recipient map so the
    canonical resolver can preserve the address. The proposal can never become live
    through this path because it is absent from the committed live sender allow-list.
    """

    mail_identity_registry.validate_registry(identities)
    if not isinstance(payload, dict):
        raise mail_identity_registry.IdentitySelectionError(
            "message payload must be an object"
        )

    system_generated = payload.get("system_generated", False)
    if not isinstance(system_generated, bool):
        raise mail_identity_registry.IdentitySelectionError(
            "system_generated must be boolean"
        )
    if system_generated:
        return mail_identity_registry.resolve_sender(identities, payload)

    original_recipient = _normalized_original_recipient(payload)
    if not original_recipient:
        return mail_identity_registry.resolve_sender(identities, payload)

    recipient_map = identities["sender_selection"]["recipient_to_sender"]
    if original_recipient in recipient_map:
        return mail_identity_registry.resolve_sender(identities, payload)

    domain = original_recipient.rsplit("@", 1)[1]
    if domain not in identities["domains"]:
        return mail_identity_registry.resolve_sender(identities, payload)

    internal_only = {
        definition["address"].casefold()
        for definition in identities["mailboxes"].values()
    }
    internal_only.add(identities["sender_selection"]["system_sender"].casefold())
    if original_recipient in internal_only:
        raise mail_identity_registry.IdentitySelectionError(
            "original recipient is an internal-only or reserved mail identity"
        )

    proposed_identities = copy.deepcopy(identities)
    proposed_identities["sender_selection"]["recipient_to_sender"][
        original_recipient
    ] = original_recipient
    selection = mail_identity_registry.resolve_sender(proposed_identities, payload)
    return mail_identity_registry.SenderSelection(
        address=selection.address,
        identity_key=None,
        reason=CATCH_ALL_PROPOSAL_REASON,
        submitted_from_present=selection.submitted_from_present,
        from_address_replaced=selection.from_address_replaced,
        live_enabled=False,
        reply_to=selection.reply_to,
    )


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

    selection = _resolve_sender_with_catchall_proposal(identities, payload)
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
    if selection.reason == CATCH_ALL_PROPOSAL_REASON:
        preview["request"]["live_delivery_block_reason"] = (
            "catch-all reply identity is proposed only and is not provider-authorized for live delivery"
        )
    return mail_threading.apply_to_preview(preview, payload)


def send_message(
    config: dict[str, Any],
    policy: dict[str, Any],
    identities: dict[str, Any],
    payload: dict[str, Any],
    *,
    confirmation: bool,
    audit_path: str | Path | None = None,
    final_scanner: Callable[[bytes], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    preview = compose_preview(config, policy, identities, payload)
    selection = preview["sender_selection"]
    if not selection["live_enabled"]:
        if selection["reason"] == CATCH_ALL_PROPOSAL_REASON:
            raise outbound_mail_gateway.DeliveryDisabledError(
                "catch-all sender identity is proposed but not authorized for live delivery"
            )
        raise outbound_mail_gateway.DeliveryDisabledError(
            "selected sender identity is not authorized for live delivery"
        )
    result = mail_secure_submission.send_preview(
        config,
        policy,
        preview,
        confirmation=confirmation,
        final_scanner=final_scanner,
    )
    event = result["audit_event"]
    event["sender_address"] = selection["address"]
    event["sender_selection_reason"] = selection["reason"]
    event["sender_identity_key"] = selection["identity_key"]
    result["sender_selection"] = selection
    if audit_path is not None and policy["audit"]["write_jsonl"]:
        outbound_mail_gateway.append_audit_event(audit_path, event)
    return result
