#!/usr/bin/env python3
"""Bounded repository adapter for WW.CX Mail Room Private AI capabilities.

This adapter supports sanitized status and draft preparation only. It never calls a
provider, never invokes the send path, and does not claim inbound correspondence
retrieval until an explicitly authorized native correspondence source is available.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import identity_aware_outbound_gateway
import mail_identity_registry
import outbound_mail_gateway
import outbound_mail_policy


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "config" / "messaging" / "outbound-mail-gateway.json"
DEFAULT_IDENTITIES = REPO_ROOT / "config" / "messaging" / "mail-identities.json"


class MailAIAdapterError(RuntimeError):
    pass


def _load(
    config_path: Path = DEFAULT_CONFIG,
    identities_path: Path = DEFAULT_IDENTITIES,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    config = outbound_mail_gateway.load_json(config_path.resolve())
    outbound_mail_gateway.validate_gateway_config(config)
    policy_path = outbound_mail_gateway.resolve_repo_path(REPO_ROOT, config["paths"]["policy"])
    policy = outbound_mail_gateway.load_json(policy_path)
    outbound_mail_policy.validate_policy(policy)
    identities = outbound_mail_gateway.load_json(identities_path.resolve())
    mail_identity_registry.validate_registry(identities)
    return config, policy, identities


def status(
    config_path: Path = DEFAULT_CONFIG,
    identities_path: Path = DEFAULT_IDENTITIES,
) -> dict[str, Any]:
    config, policy, identities = _load(config_path, identities_path)
    payload = identity_aware_outbound_gateway.status_payload(config, policy, identities)
    return {
        "contract": "wwcx.mail-ai-status.v1",
        "capabilities": ["mail.status.read", "mail.draft.prepare"],
        "pending_capabilities": ["mail.correspondence.read"],
        "gateway": payload,
        "content_is_untrusted": True,
        "send_authorized": False,
        "mutation_authorized": False,
    }


def prepare_draft(
    request: dict[str, Any],
    *,
    config_path: Path = DEFAULT_CONFIG,
    identities_path: Path = DEFAULT_IDENTITIES,
) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise MailAIAdapterError("mail draft request must be an object")
    config, policy, identities = _load(config_path, identities_path)
    preview = identity_aware_outbound_gateway.compose_preview(
        config,
        policy,
        identities,
        copy.deepcopy(request),
    )
    preview.pop("action_token", None)
    result = {
        "contract": "wwcx.mail-ai-draft.v1",
        "state": "drafted",
        "ai_generated": True,
        "delivery_status": "prepared_not_sent",
        "network_activity": False,
        "external_delivery_attempted": False,
        "send_authorized": False,
        "mutation_authorized": False,
        "draft": preview,
    }
    if result["draft"].get("action_token") is not None:
        raise MailAIAdapterError("mail draft leaked an action token")
    return result


def correspondence_read_state() -> dict[str, Any]:
    """Describe the intentionally closed correspondence-read boundary."""
    return {
        "contract": "wwcx.mail-correspondence-read-state.v1",
        "capability": "mail.correspondence.read",
        "state": "blocked_pending_authoritative_source",
        "reason": (
            "No channel-neutral adapter is permitted to invent correspondence from outbound audit metadata; "
            "an explicitly authorized native Mail Room correspondence source is required."
        ),
        "mutation_authorized": False,
    }
