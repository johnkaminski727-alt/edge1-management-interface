"""
Authenticated browser adapter for Unified Contacts CRUD.

Browser code never receives the Operations API credential.
The Edge1 authenticated HTTP service supplies session
authentication, authorization, CSRF validation, and the
server-side Operations client.
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
    AuthorizationError,
    GatewayError,
)


CONTACTS_CRUD_SCOPE = "edge1.contacts.manage"

ACTION_MAP = {
    "entity.create": "contacts.entity.create",
    "entity.update": "contacts.entity.update",
    "entity.archive": "contacts.entity.archive",
    "entity.restore": "contacts.entity.restore",
    "entity.merge": "contacts.entity.merge",
    "discovery.promote": "contacts.discovery.promote",
    "maintenance.relationship.approve": "contacts.maintenance.relationship.approve",
    "maintenance.relationship.reject": "contacts.maintenance.relationship.reject",
    "point.add": "contacts.point.add",
    "point.update": "contacts.point.update",
    "point.detach": "contacts.point.detach",
}


@dataclass(frozen=True)
class ContactsCrudResult:
    status_code: int
    payload: Mapping[str, Any]


class ContactsCrudAdapter:
    """
    Session-authenticated, CSRF-protected Contacts CRUD bridge.
    """

    PREFIX = "/edge1-ops/api/v1/contacts/crud/"

    def __init__(
        self,
        gateway,
        operations: Edge1OperationsClient,
    ):
        self.gateway = gateway
        self.operations = operations

    @classmethod
    def parse_path(cls, path: str):
        if (
            not isinstance(path, str)
            or not path.startswith(cls.PREFIX)
        ):
            return None

        tail = path[len(cls.PREFIX):]

        if "?" in tail or "#" in tail:
            raise ValueError("path_invalid")

        if tail not in ACTION_MAP:
            return None

        return tail

    @staticmethod
    def parse_payload(body: bytes):
        try:
            payload = json.loads(
                (body or b"{}").decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError("json_invalid") from exc

        if not isinstance(payload, dict):
            raise ValueError("payload_invalid")

        # The typed Operations validators remain authoritative
        # for per-action schema validation. Reject structures
        # that cannot safely cross this adapter.
        for key in payload:
            if (
                not isinstance(key, str)
                or not key
            ):
                raise ValueError("payload_invalid")

        return payload

    def mutate(
        self,
        *,
        session_token: str,
        request_id: str,
        csrf_validated: bool,
        operation: str,
        parameters: Mapping[str, Any],
    ) -> ContactsCrudResult:

        if not csrf_validated:
            raise AuthorizationError(
                "csrf_required"
            )

        action = ACTION_MAP.get(operation)

        if action is None:
            raise ValueError(
                "operation_invalid"
            )

        context = self.gateway.authorize_action(
            session_token,
            action,
            request_id,
        )

        # Preserve the browser's logical mutation identity across
        # transport retries, but validate and namespace it at this
        # authenticated boundary before it reaches Operations.
        operation_parameters = dict(parameters)
        browser_key = operation_parameters.pop(
            "idempotency_key",
            None,
        )

        if (
            not isinstance(browser_key, str)
            or len(browser_key) < 16
            or len(browser_key) > 96
            or not all(
                character.isalnum()
                or character in "._:-"
                for character in browser_key
            )
        ):
            raise ValueError("idempotency_key_invalid")

        operation_parameters["idempotency_key"] = (
            "contacts-crud:" + browser_key
        )

        try:
            result = self.operations.run(
                action,
                context.subject,
                parameters=operation_parameters,
            )
        except TypeError as exc:
            raise GatewayError(
                "contacts_operations_client_incompatible"
            ) from exc
        except OperationsClientTimeout as exc:
            raise GatewayError(
                "contacts_operations_timeout"
            ) from exc
        except OperationsClientError as exc:
            raise GatewayError(
                "contacts_operations_unavailable"
            ) from exc

        payload = {
            "operation": operation,
            "action": result.action_id,
            "status": result.status,
            "message": result.message,
            "event_id": result.event_id,
            "request_id": request_id,
        }

        if result.status == "succeeded":
            typed_result = result.result or {}

            for key in (
                "entity_id",
                "contact_point_id",
                "assertion_id",
            ):
                value = typed_result.get(key)

                if value is not None:
                    if (
                        not isinstance(value, int)
                        or isinstance(value, bool)
                        or value < 1
                    ):
                        raise GatewayError(
                            "contacts_operations_result_invalid"
                        )

                    payload[key] = value

        return ContactsCrudResult(
            status_code=(
                200
                if result.status == "succeeded"
                else 409
            ),
            payload=payload,
        )


__all__ = [
    "ACTION_MAP",
    "CONTACTS_CRUD_SCOPE",
    "ContactsCrudAdapter",
    "ContactsCrudResult",
]
