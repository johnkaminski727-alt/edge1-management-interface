#!/usr/bin/env python3
"""Bounded WW.CX Mail Room Private AI capabilities.

Draft preparation remains local and never sends. Correspondence reads are disabled by
default and become available only when a private persisted store exists and the selected
records carry immutable authoritative `local_native` or `production_native` provenance.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import identity_aware_outbound_gateway
import mail_identity_registry
import outbound_mail_gateway
import outbound_mail_policy
from mail_correspondence_store import (
    READABLE_AUTHORITATIVE_SCOPES,
    CorrespondenceStoreError,
    MailCorrespondenceStore,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "config" / "messaging" / "outbound-mail-gateway.json"
DEFAULT_IDENTITIES = REPO_ROOT / "config" / "messaging" / "mail-identities.json"
PRIVATE_CORRESPONDENCE_ROOT = Path("/var/lib/wwcx-mail-room")
DEFAULT_CORRESPONDENCE_DB = PRIVATE_CORRESPONDENCE_ROOT / "correspondence.sqlite3"
CORRESPONDENCE_ENABLE_ENV = "WWCX_MAIL_CORRESPONDENCE_READ_ENABLED"
CORRESPONDENCE_DB_ENV = "WWCX_MAIL_CORRESPONDENCE_DB"


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


def _correspondence_enabled(enabled: bool | None = None) -> bool:
    if enabled is not None:
        return bool(enabled)
    return os.getenv(CORRESPONDENCE_ENABLE_ENV, "false").strip().casefold() == "true"


def _runtime_db_path(configured: str) -> Path:
    candidate = Path(configured).absolute()
    try:
        candidate.relative_to(PRIVATE_CORRESPONDENCE_ROOT)
    except ValueError as exc:
        raise MailAIAdapterError(
            "runtime correspondence database must remain under /var/lib/wwcx-mail-room"
        ) from exc
    return candidate


def _correspondence_db(path: Path | None = None) -> Path:
    # Explicit path injection is reserved for local tests/internal calls. Runtime
    # configuration is constrained to the private Mail Room root.
    if path is not None:
        return Path(path).absolute()
    configured = os.getenv(CORRESPONDENCE_DB_ENV, "").strip()
    return _runtime_db_path(configured) if configured else DEFAULT_CORRESPONDENCE_DB


def _read_store(path: Path) -> MailCorrespondenceStore:
    try:
        return MailCorrespondenceStore(
            path,
            source="mail-ai-read-adapter",
            source_authoritative=False,
            source_scope="synthetic",
            read_only=True,
        )
    except CorrespondenceStoreError as exc:
        raise MailAIAdapterError(str(exc)) from exc


def _record_is_authorized(record: dict[str, Any]) -> bool:
    provenance = record.get("provenance")
    return bool(
        isinstance(provenance, dict)
        and provenance.get("authoritative") is True
        and provenance.get("scope") in READABLE_AUTHORITATIVE_SCOPES
    )


def _state_is_ready(state: dict[str, Any]) -> bool:
    return str(state.get("state", "")).startswith("ready_")


def correspondence_read_state(
    *,
    db_path: Path | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    try:
        resolved_db = _correspondence_db(db_path)
    except MailAIAdapterError as exc:
        return {
            "contract": "wwcx.mail-correspondence-read-state.v1",
            "capability": "mail.correspondence.read",
            "read_enabled": _correspondence_enabled(enabled),
            "state": "blocked_store_invalid",
            "reason": str(exc),
            "production_provider_ready": False,
            "content_is_untrusted": True,
            "send_authorized": False,
            "mutation_authorized": False,
        }
    is_enabled = _correspondence_enabled(enabled)
    base = {
        "contract": "wwcx.mail-correspondence-read-state.v1",
        "capability": "mail.correspondence.read",
        "read_enabled": is_enabled,
        "store_location": "private_mail_room_root",
        "repository_foundation": "server/mail_correspondence_store.py",
        "content_is_untrusted": True,
        "send_authorized": False,
        "mutation_authorized": False,
    }
    if not is_enabled:
        return {
            **base,
            "state": "blocked_configuration_disabled",
            "reason": (
                "Correspondence reads are disabled until an approved private source/store is selected."
            ),
            "production_provider_ready": False,
        }
    if resolved_db.is_symlink() or not resolved_db.is_file():
        return {
            **base,
            "state": "blocked_store_unavailable",
            "reason": "The configured private correspondence database is unavailable.",
            "production_provider_ready": False,
        }
    try:
        store_status = _read_store(resolved_db).status()
    except MailAIAdapterError as exc:
        return {
            **base,
            "state": "blocked_store_invalid",
            "reason": str(exc),
            "production_provider_ready": False,
        }
    authorized_sources = [
        item
        for item in store_status["sources"]
        if item["authoritative"] is True and item["scope"] in READABLE_AUTHORITATIVE_SCOPES
    ]
    if not authorized_sources:
        return {
            **base,
            "state": "blocked_no_authoritative_records",
            "reason": (
                "The store contains no records from an authoritative local or production-native source."
            ),
            "record_count": store_status["record_count"],
            "production_provider_ready": False,
        }
    scopes = sorted({str(item["scope"]) for item in authorized_sources})
    production_ready = "production_native" in scopes
    state = "ready_production_native" if production_ready else "ready_local_native"
    return {
        **base,
        "state": state,
        "record_count": store_status["record_count"],
        "authoritative_scopes": scopes,
        "production_provider_ready": production_ready,
        "source_truth": "provider_native" if production_ready else "local_native_only",
    }


def status(
    config_path: Path = DEFAULT_CONFIG,
    identities_path: Path = DEFAULT_IDENTITIES,
    *,
    correspondence_db_path: Path | None = None,
    correspondence_enabled: bool | None = None,
) -> dict[str, Any]:
    config, policy, identities = _load(config_path, identities_path)
    payload = identity_aware_outbound_gateway.status_payload(config, policy, identities)
    correspondence = correspondence_read_state(
        db_path=correspondence_db_path,
        enabled=correspondence_enabled,
    )
    capabilities = ["mail.status.read", "mail.draft.prepare"]
    pending: list[str] = []
    if _state_is_ready(correspondence):
        capabilities.append("mail.correspondence.read")
    else:
        pending.append("mail.correspondence.read")
    return {
        "contract": "wwcx.mail-ai-status.v1",
        "capabilities": capabilities,
        "pending_capabilities": pending,
        "gateway": payload,
        "correspondence": correspondence,
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


def _require_correspondence_ready(
    db_path: Path | None,
    enabled: bool | None,
) -> MailCorrespondenceStore:
    resolved_db = _correspondence_db(db_path)
    state = correspondence_read_state(db_path=resolved_db, enabled=enabled)
    if not _state_is_ready(state):
        raise MailAIAdapterError(str(state.get("reason", "correspondence read is unavailable")))
    return _read_store(resolved_db)


def read_correspondence_message(
    message_id: str,
    *,
    db_path: Path | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    store = _require_correspondence_ready(db_path, enabled)
    try:
        record = store.read_message(message_id)
    except CorrespondenceStoreError as exc:
        raise MailAIAdapterError(str(exc)) from exc
    if not _record_is_authorized(record):
        raise MailAIAdapterError("correspondence record is not authorized for Private AI read")
    scope = str(record["provenance"]["scope"])
    return {
        "contract": "wwcx.mail-ai-correspondence-message-read.v1",
        "message": record,
        "source_scope": scope,
        "production_provider_ready": scope == "production_native",
        "content_is_untrusted": True,
        "send_authorized": False,
        "mutation_authorized": False,
    }


def read_correspondence_thread(
    thread_id: str,
    *,
    limit: int = 50,
    db_path: Path | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    store = _require_correspondence_ready(db_path, enabled)
    try:
        thread = store.read_thread(thread_id, limit=limit)
    except CorrespondenceStoreError as exc:
        raise MailAIAdapterError(str(exc)) from exc
    if not all(_record_is_authorized(item) for item in thread["messages"]):
        raise MailAIAdapterError("thread contains records not authorized for Private AI read")
    scopes = sorted({str(item["provenance"]["scope"]) for item in thread["messages"]})
    return {
        "contract": "wwcx.mail-ai-correspondence-thread-read.v1",
        "thread": thread,
        "source_scopes": scopes,
        "production_provider_ready": bool(scopes) and set(scopes) == {"production_native"},
        "content_is_untrusted": True,
        "send_authorized": False,
        "mutation_authorized": False,
    }
