#!/usr/bin/env python3

"""Internal-only API adapter for Phase 13I carrier-support review.

This module authorizes queue reads and non-executing lifecycle review events.
Carrier identities are rejected even when internal scopes are misconfigured.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .carrier_review import (
        REVIEW_READ_SCOPE,
        REVIEW_WRITE_SCOPE,
        append_review_event,
        build_review_queue,
    )
except ImportError:  # Direct script/server execution
    from carrier_review import (
        REVIEW_READ_SCOPE,
        REVIEW_WRITE_SCOPE,
        append_review_event,
        build_review_queue,
    )

REVIEW_QUEUE_ENDPOINT = "/portal/internal/carrier-review/queue"
REVIEW_ACTION_ENDPOINT = "/portal/internal/carrier-review/events"


class ReviewAuthorizationError(PermissionError):
    """Raised when a portal identity cannot use the internal review API."""


def authorize_internal_review(identity: Any, required_scope: str) -> None:
    """Require an internal identity with the exact review scope.

    A configured carrier ID always marks the identity as carrier-originated and
    therefore ineligible for internal review access, even if a scope was
    accidentally assigned.
    """

    if identity is None:
        raise ReviewAuthorizationError("authentication failed")
    if getattr(identity, "carrier_id", None):
        raise ReviewAuthorizationError("carrier identities are not permitted")
    scopes = getattr(identity, "scopes", frozenset())
    if required_scope not in scopes:
        raise ReviewAuthorizationError("scope denied")


def review_queue_response(
    identity: Any,
    ticket_path: Path,
    change_path: Path,
    review_path: Path,
) -> dict[str, Any]:
    authorize_internal_review(identity, REVIEW_READ_SCOPE)
    return build_review_queue(ticket_path, change_path, review_path)


def create_review_event(
    identity: Any,
    review_path: Path,
    ticket_path: Path,
    change_path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    authorize_internal_review(identity, REVIEW_WRITE_SCOPE)
    return append_review_event(
        review_path,
        ticket_path,
        change_path,
        identity.client_id,
        payload,
    )
