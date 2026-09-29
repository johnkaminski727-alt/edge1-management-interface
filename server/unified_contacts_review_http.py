"""
Authenticated browser adapter for Unified Contacts candidate review.

This module deliberately does not expose the Operations API credential
to browser code. Authentication and authorization are supplied by the
existing Edge1 session gateway; mutation execution is delegated to the
existing typed Operations API actions.

This is source-only until separately activated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from server.edge1_operations_client import (
    Edge1OperationsClient,
    OperationsClientError,
    OperationsClientTimeout,
)
from server.edge1_security_auth_core import (
    AuthenticationError,
    AuthorizationError,
    GatewayError,
)
from server.edge1_security_auth_http_types import (
    HttpRequest,
    HttpResponse,
)


CONTACTS_REVIEW_SCOPE = "edge1.contacts.relationships.review"

ACTION_MAP = {
    "accept": "contacts.correlation.accept",
    "reject": "contacts.correlation.reject",
    "promote": "contacts.correlation.promote",
}


@dataclass(frozen=True)
class ContactsReviewResult:
    status_code: int
    payload: Mapping[str, Any]


class ContactsReviewAdapter:
    """
    Session-authenticated, CSRF-protected Contacts review bridge.

    The containing authenticated HTTP service supplies:
      - gateway
      - operations
      - session-token extraction
      - CSRF validation
      - same-origin validation
      - JSON response construction
    """

    def __init__(self, gateway, operations: Edge1OperationsClient):
        self.gateway = gateway
        self.operations = operations

    @staticmethod
    def parse_path(path: str):
        prefix = "/edge1-ops/api/v1/contacts/correlations/"

        if not isinstance(path, str) or not path.startswith(prefix):
            return None

        tail = path[len(prefix):]

        if "?" in tail or "#" in tail:
            raise ValueError("path_invalid")

        pieces = tail.split("/")

        if len(pieces) != 2:
            return None

        candidate_raw, operation = pieces

        if (
            not candidate_raw.isdigit()
            or candidate_raw.startswith("0")
        ):
            raise ValueError("candidate_id_invalid")

        candidate_id = int(candidate_raw)

        if candidate_id < 1:
            raise ValueError("candidate_id_invalid")

        if operation not in ACTION_MAP:
            return None

        return candidate_id, operation

    @staticmethod
    def parse_payload(operation: str, body: bytes):
        try:
            payload = json.loads(
                (body or b"{}").decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("json_invalid") from exc

        if not isinstance(payload, dict):
            raise ValueError("payload_invalid")

        if operation in {"accept", "reject"}:
            if payload:
                raise ValueError("payload_invalid")

            return {}

        allowed = {
            "provenance_id",
            "evidence_role",
            "evidence_summary",
        }

        if not set(payload).issubset(allowed):
            raise ValueError("payload_invalid")

        provenance_id = payload.get("provenance_id")

        if (
            isinstance(provenance_id, bool)
            or not isinstance(provenance_id, int)
            or provenance_id < 1
        ):
            raise ValueError("provenance_id_invalid")

        parameters = {
            "provenance_id": provenance_id,
        }

        if "evidence_role" in payload:
            role = payload["evidence_role"]

            if not isinstance(role, str):
                raise ValueError("evidence_role_invalid")

            parameters["evidence_role"] = role

        if "evidence_summary" in payload:
            summary = payload["evidence_summary"]

            if not isinstance(summary, str):
                raise ValueError("evidence_summary_invalid")

            parameters["evidence_summary"] = summary

        return parameters

    def review(
        self,
        *,
        session_token: str,
        request_id: str,
        csrf_validated: bool,
        candidate_id: int,
        operation: str,
        parameters: Mapping[str, Any],
    ) -> ContactsReviewResult:

        if not csrf_validated:
            raise AuthorizationError("csrf_required")

        context = self.gateway.authenticate_session(
            session_token,
            request_id,
        )

        if CONTACTS_REVIEW_SCOPE not in context.scopes:
            raise AuthorizationError(
                "contacts_review_scope_required"
            )

        action = ACTION_MAP.get(operation)

        if action is None:
            raise ValueError("operation_invalid")

        body = {
            "candidate_id": candidate_id,
            **dict(parameters),
        }

        try:
            result = self.operations.run(
                action,
                context.subject,
                parameters=body,
            )
        except TypeError:
            # Existing Operations client versions may expose
            # a fixed-action run signature only. Fail closed rather
            # than attempting a browser-visible workaround.
            raise GatewayError(
                "contacts_operations_client_incompatible"
            )
        except OperationsClientTimeout as exc:
            raise GatewayError(
                "contacts_operations_timeout"
            ) from exc
        except OperationsClientError as exc:
            raise GatewayError(
                "contacts_operations_unavailable"
            ) from exc

        return ContactsReviewResult(
            status_code=(
                200
                if result.status == "succeeded"
                else 409
            ),
            payload={
                "candidate_id": candidate_id,
                "operation": operation,
                "action": result.action_id,
                "status": result.status,
                "message": result.message,
                "event_id": result.event_id,
                "request_id": request_id,
            },
        )


__all__ = [
    "ACTION_MAP",
    "CONTACTS_REVIEW_SCOPE",
    "ContactsReviewAdapter",
    "ContactsReviewResult",
]
