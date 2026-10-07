import json
import unittest
from pathlib import Path

from server.edge1_operations_client import ACTION_PATHS
from server.unified_contacts_crud_http import ACTION_MAP
from server.edge1_operations_typed_actions import (
    TYPED_ACTION_HANDLERS,
    TYPED_ACTION_VALIDATORS,
)


EXPECTED = {
    "entity.create": (
        "contacts.entity.create",
        "contacts_entity_create",
    ),
    "entity.update": (
        "contacts.entity.update",
        "contacts_entity_update",
    ),
    "entity.archive": (
        "contacts.entity.archive",
        "contacts_entity_archive",
    ),
    "entity.restore": (
        "contacts.entity.restore",
        "contacts_entity_restore",
    ),
    "entity.merge": (
        "contacts.entity.merge",
        "contacts_entity_merge",
    ),
    "discovery.promote": (
        "contacts.discovery.promote",
        "contacts_discovery_promote",
    ),
    "maintenance.relationship.approve": (
        "contacts.maintenance.relationship.approve",
        "contacts_maintenance_relationship_approve",
    ),
    "maintenance.relationship.reject": (
        "contacts.maintenance.relationship.reject",
        "contacts_maintenance_relationship_reject",
    ),
    "point.add": (
        "contacts.point.add",
        "contacts_point_add",
    ),
    "point.update": (
        "contacts.point.update",
        "contacts_point_update",
    ),
    "point.detach": (
        "contacts.point.detach",
        "contacts_point_detach",
    ),
}


def allowlist():
    return json.loads(
        Path(
            "config/edge1-operations-allowlist.json"
        ).read_text(encoding="utf-8")
    )["actions"]


class UnifiedContactsCrudContractTests(unittest.TestCase):

    def test_browser_adapter_exposes_exact_crud_contract(self):
        assert set(ACTION_MAP) == set(EXPECTED)

        for browser_action, (operation, _) in EXPECTED.items():
            assert ACTION_MAP[browser_action] == operation


    def test_operations_client_exposes_every_crud_action(self):
        for operation, _ in EXPECTED.values():
            assert ACTION_PATHS[operation] == (
                f"/v1/actions/{operation}/run"
            )


    def test_every_crud_action_is_typed_and_gated(self):
        actions = allowlist()

        for operation, (_, handler) in {
            op: (op, handler)
            for _, (op, handler) in EXPECTED.items()
        }.items():
            config = actions[operation]

            assert config["typed_handler"] == handler
            assert config["mutating"] is True
            assert (
                config["mutation_gate"]
                == "contacts_crud_mutations"
            )


    def test_every_crud_handler_and_validator_is_registered(self):
        for _, handler in EXPECTED.values():
            assert handler in TYPED_ACTION_HANDLERS
            assert handler in TYPED_ACTION_VALIDATORS


    def test_no_browser_operation_bypasses_operations_action(self):
        expected_operations = {
            operation
            for operation, _ in EXPECTED.values()
        }

        assert set(ACTION_MAP.values()) == expected_operations


    def test_crud_contract_is_exactly_eleven_operations(self):
        assert len(EXPECTED) == 11


class UnifiedContactsCrudIdempotencyTests(unittest.TestCase):

    class _Context:
        subject = "crud-test"

    class _Gateway:
        def authorize_action(
            self,
            session_token,
            action,
            request_id,
        ):
            return UnifiedContactsCrudIdempotencyTests._Context()

    class _Result:
        action_id = "contacts.entity.create"
        status = "succeeded"
        message = "ok"
        event_id = "crud-test-event"
        result = {"entity_id": 999}

    class _Operations:
        def __init__(self):
            self.calls = []

        def run(
            self,
            action,
            subject,
            *,
            parameters=None,
        ):
            self.calls.append(
                (action, subject, dict(parameters or {}))
            )
            return UnifiedContactsCrudIdempotencyTests._Result()

    def _adapter(self):
        from server.unified_contacts_crud_http import (
            ContactsCrudAdapter,
        )

        operations = self._Operations()

        return (
            ContactsCrudAdapter(
                self._Gateway(),
                operations,
            ),
            operations,
        )

    def test_browser_logical_id_survives_transport_retry(self):
        adapter, operations = self._adapter()

        parameters = {
            "entity_type": "person",
            "canonical_name": "Retry Test",
            "idempotency_key":
                "contacts-entity.create-"
                "11111111-1111-4111-8111-111111111111",
        }

        for request_id in (
            "edge1-http-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "edge1-http-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ):
            adapter.mutate(
                session_token="x" * 32,
                request_id=request_id,
                csrf_validated=True,
                operation="entity.create",
                parameters=parameters,
            )

        self.assertEqual(len(operations.calls), 2)

        first = operations.calls[0][2]["idempotency_key"]
        second = operations.calls[1][2]["idempotency_key"]

        self.assertEqual(first, second)
        self.assertEqual(
            first,
            "contacts-crud:"
            + parameters["idempotency_key"],
        )

    def test_different_logical_mutations_get_different_keys(self):
        adapter, operations = self._adapter()

        for suffix in ("aaaaaaaa", "bbbbbbbb"):
            adapter.mutate(
                session_token="x" * 32,
                request_id="edge1-http-" + suffix * 4,
                csrf_validated=True,
                operation="entity.create",
                parameters={
                    "entity_type": "person",
                    "canonical_name": "Distinct Test",
                    "idempotency_key":
                        "contacts-entity.create-" + suffix * 4,
                },
            )

        keys = [
            call[2]["idempotency_key"]
            for call in operations.calls
        ]

        self.assertNotEqual(keys[0], keys[1])

    def test_invalid_browser_idempotency_key_is_rejected(self):
        adapter, operations = self._adapter()

        with self.assertRaisesRegex(
            ValueError,
            "idempotency_key_invalid",
        ):
            adapter.mutate(
                session_token="x" * 32,
                request_id=(
                    "edge1-http-"
                    "cccccccccccccccccccccccccccccccc"
                ),
                csrf_validated=True,
                operation="entity.create",
                parameters={
                    "entity_type": "person",
                    "canonical_name": "Invalid Key",
                    "idempotency_key": "../bad key",
                },
            )

        self.assertEqual(operations.calls, [])
