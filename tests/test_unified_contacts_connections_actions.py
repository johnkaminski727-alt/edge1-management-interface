import json
import pathlib
import tempfile
import unittest
from unittest import mock

from server import edge1_operations_api as api
from server import edge1_operations_typed_actions as typed


ROOT = pathlib.Path(__file__).resolve().parents[1]
ALLOWLIST = json.loads(
    (
        ROOT / "config/edge1-operations-allowlist.json"
    ).read_text()
)
SERVICE = (
    ROOT / "deploy/edge1-operations-api.service"
).read_text()


class ContactsConnectionActionTests(unittest.TestCase):
    def test_actions_are_typed_mutations_with_dedicated_gate(self):
        for operation in (
            "accept",
            "reject",
            "promote",
        ):
            action = ALLOWLIST["actions"][
                f"contacts.correlation.{operation}"
            ]

            self.assertTrue(action["mutating"])
            self.assertEqual(
                action["mutation_gate"],
                "contacts_relationship_mutations",
            )
            self.assertNotIn("argv", action)
            self.assertNotIn("cwd", action)

    def test_gate_defaults_off_in_service(self):
        self.assertIn(
            "Environment="
            "EDGE1_OPS_CONTACTS_RELATIONSHIP_WRITES_ENABLED="
            "false\n",
            SERVICE,
        )

    def test_gate_is_known_and_disabled_by_default(self):
        self.assertEqual(
            api.MUTATION_GATE_ENV[
                "contacts_relationship_mutations"
            ],
            "EDGE1_OPS_CONTACTS_RELATIONSHIP_WRITES_ENABLED",
        )

        with mock.patch.dict(
            api.os.environ,
            {
                "EDGE1_OPS_CONTACTS_RELATIONSHIP_WRITES_ENABLED":
                "false"
            },
            clear=False,
        ):
            self.assertFalse(
                api._gate_enabled(
                    "contacts_relationship_mutations"
                )
            )

    def test_accept_validator_is_minimal(self):
        value = typed.validate_typed_handler(
            "contacts_candidate_accept",
            {
                "candidate_id": 7,
                "idempotency_key": "contacts-accept-0001",
            },
        )

        self.assertEqual(value["candidate_id"], 7)

        with self.assertRaises(
            typed.TypedActionValidationError
        ):
            typed.validate_typed_handler(
                "contacts_candidate_accept",
                {
                    "candidate_id": 7,
                    "idempotency_key":
                    "contacts-accept-0002",
                    "sql": "DELETE FROM anything",
                },
            )

    def test_promote_requires_provenance(self):
        with self.assertRaises(
            typed.TypedActionValidationError
        ):
            typed.validate_typed_handler(
                "contacts_candidate_promote",
                {
                    "candidate_id": 7,
                    "idempotency_key":
                    "contacts-promote-0001",
                },
            )

        value = typed.validate_typed_handler(
            "contacts_candidate_promote",
            {
                "candidate_id": 7,
                "provenance_id": 20,
                "idempotency_key":
                "contacts-promote-0002",
            },
        )

        self.assertEqual(value["provenance_id"], 20)
        self.assertEqual(
            value["evidence_role"],
            "supporting",
        )

    def test_disabled_gate_blocks_before_handler(self):
        with mock.patch.object(
            api,
            "load_allowlist",
            return_value=ALLOWLIST["actions"],
        ):
            with mock.patch.object(
                api,
                "_gate_enabled",
                return_value=False,
            ):
                with self.assertRaises(PermissionError):
                    api.safe_typed_action(
                        "contacts.correlation.accept"
                    )


if __name__ == "__main__":
    unittest.main()


class ContactsActionPipelineIntegrationTests(
    unittest.TestCase
):
    def test_action_pipeline_gate_and_handler_contract(self):
        import sqlite3

        from tools.unified_contacts.schema_connections import (
            migrate,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            contacts_db = root / "contacts.sqlite"

            db = sqlite3.connect(contacts_db)
            db.execute("PRAGMA foreign_keys=ON")

            db.executescript(
                """
                CREATE TABLE contact_entities (
                    id INTEGER PRIMARY KEY
                );

                CREATE TABLE contact_points (
                    id INTEGER PRIMARY KEY
                );

                CREATE TABLE provenance_records (
                    id INTEGER PRIMARY KEY,
                    verification_status TEXT NOT NULL
                );

                CREATE TABLE candidate_correlations (
                    id INTEGER PRIMARY KEY,
                    left_entity_id INTEGER,
                    right_entity_id INTEGER,
                    left_contact_point_id INTEGER,
                    right_contact_point_id INTEGER,
                    correlation_type TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    rationale TEXT,
                    review_status TEXT NOT NULL
                        DEFAULT 'pending',
                    reviewed_at TEXT,
                    created_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            db.executemany(
                """
                INSERT INTO contact_entities(id)
                VALUES (?)
                """,
                [(1,), (2,)],
            )

            db.execute(
                """
                INSERT INTO provenance_records(
                    id,
                    verification_status
                )
                VALUES (20, 'document_sourced')
                """
            )

            migrate(db)

            candidate_id = db.execute(
                """
                INSERT INTO candidate_correlations(
                    left_entity_id,
                    right_entity_id,
                    correlation_type,
                    confidence,
                    review_status,
                    rationale
                )
                VALUES (
                    1,
                    2,
                    'vendor_of',
                    'probable',
                    'pending',
                    'pipeline integration test'
                )
                """
            ).lastrowid

            db.commit()
            db.close()

            original_connect = typed.sqlite3.connect

            def routed_connect(path, *args, **kwargs):
                if str(path).endswith(
                    "/phone-intelligence.sqlite"
                ):
                    return original_connect(
                        contacts_db,
                        *args,
                        **kwargs,
                    )

                return original_connect(
                    path,
                    *args,
                    **kwargs,
                )

            parameters = {
                "candidate_id": candidate_id,
                "idempotency_key":
                "contacts-pipeline-accept-0001",
            }

            validated = typed.validate_typed_handler(
                "contacts_candidate_accept",
                parameters,
            )

            self.assertEqual(
                validated["candidate_id"],
                candidate_id,
            )

            with mock.patch.object(
                typed.sqlite3,
                "connect",
                side_effect=routed_connect,
            ):
                result = typed.run_typed_handler(
                    "contacts_candidate_accept",
                    validated,
                )

            self.assertEqual(
                result["candidate_id"],
                candidate_id,
            )

            self.assertEqual(
                result["operation"],
                "accept",
            )

            self.assertEqual(
                result["review_status"],
                "accepted",
            )

            verify = sqlite3.connect(contacts_db)

            status = verify.execute(
                """
                SELECT review_status
                FROM candidate_correlations
                WHERE id=?
                """,
                (candidate_id,),
            ).fetchone()[0]

            verify.close()

            self.assertEqual(
                status,
                "accepted",
            )

    def test_contacts_actions_remain_gate_blocked(self):
        for operation in (
            "accept",
            "reject",
            "promote",
        ):
            name = (
                f"contacts.correlation.{operation}"
            )

            with mock.patch.object(
                api,
                "_gate_enabled",
                return_value=False,
            ):
                with self.assertRaises(
                    PermissionError
                ):
                    api.safe_typed_action(name)
