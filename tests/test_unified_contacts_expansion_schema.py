import sqlite3
import unittest

from tools.unified_contacts.schema_contacts_expansion import (
    apply_schema,
)


BASE = """
PRAGMA foreign_keys = ON;

CREATE TABLE contact_entities (
    id INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL
);

CREATE TABLE contact_points (
    id INTEGER PRIMARY KEY,
    normalized_value TEXT NOT NULL
);

CREATE TABLE provenance_records (
    id INTEGER PRIMARY KEY,
    source_name TEXT NOT NULL
);
"""


class ExpansionSchemaTests(unittest.TestCase):

    def database(self):
        db = sqlite3.connect(":memory:")
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(BASE)
        apply_schema(db)
        return db

    def test_schema_is_idempotent(self):
        db = self.database()
        apply_schema(db)

        names = {
            row[0]
            for row in db.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                """
            )
        }

        self.assertIn(
            "contact_entity_aliases",
            names,
        )

        self.assertIn(
            "contact_attestations",
            names,
        )

    def test_alias_round_trip(self):
        db = self.database()

        db.execute(
            """
            INSERT INTO contact_entities
                (id, canonical_name)
            VALUES
                (1, 'Example Inc.')
            """
        )

        db.execute(
            """
            INSERT INTO provenance_records
                (id, source_name)
            VALUES
                (1, 'registry')
            """
        )

        db.execute(
            """
            INSERT INTO contact_entity_aliases (
                entity_id,
                alias_name,
                alias_type,
                confidence,
                provenance_id,
                source_path
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "Example",
                "operating_name",
                "document_sourced",
                1,
                "$.domains.example",
            ),
        )

        row = db.execute(
            """
            SELECT
                alias_name,
                alias_type,
                confidence,
                source_path
            FROM contact_entity_aliases
            """
        ).fetchone()

        self.assertEqual(
            row,
            (
                "Example",
                "operating_name",
                "document_sourced",
                "$.domains.example",
            ),
        )

    def test_attestation_requires_exactly_one_subject(self):
        db = self.database()

        db.execute(
            """
            INSERT INTO contact_entities
                (id, canonical_name)
            VALUES
                (1, 'Example Inc.')
            """
        )

        db.execute(
            """
            INSERT INTO contact_points
                (id, normalized_value)
            VALUES
                (1, 'support@example.com')
            """
        )

        db.execute(
            """
            INSERT INTO provenance_records
                (id, source_name)
            VALUES
                (1, 'registry')
            """
        )

        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            db.execute(
                """
                INSERT INTO contact_attestations (
                    entity_id,
                    contact_point_id,
                    provenance_id,
                    attribute,
                    attested_value,
                    source_path
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    1,
                    1,
                    "identity_name",
                    "Example",
                    "$.example",
                ),
            )

        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            db.execute(
                """
                INSERT INTO contact_attestations (
                    provenance_id,
                    attribute,
                    attested_value,
                    source_path
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    1,
                    "identity_name",
                    "Example",
                    "$.example",
                ),
            )

    def test_attestation_round_trip(self):
        db = self.database()

        db.execute(
            """
            INSERT INTO contact_points
                (id, normalized_value)
            VALUES
                (1, 'support@example.com')
            """
        )

        db.execute(
            """
            INSERT INTO provenance_records
                (id, source_name)
            VALUES
                (1, 'registry')
            """
        )

        db.execute(
            """
            INSERT INTO contact_attestations (
                contact_point_id,
                provenance_id,
                attribute,
                attested_value,
                classification,
                verification_status,
                source_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                1,
                "email_classification",
                "support@example.com",
                "work_role",
                "document_sourced",
                "$.sender_profiles.support",
            ),
        )

        row = db.execute(
            """
            SELECT
                attribute,
                attested_value,
                classification,
                verification_status,
                source_path
            FROM contact_attestations
            """
        ).fetchone()

        self.assertEqual(
            row,
            (
                "email_classification",
                "support@example.com",
                "work_role",
                "document_sourced",
                "$.sender_profiles.support",
            ),
        )


if __name__ == "__main__":
    unittest.main()
