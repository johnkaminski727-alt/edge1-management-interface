import sqlite3
import unittest

from tools.unified_contacts.schema_connections import (
    harden_relationship_constraints,
    migrate,
)


BASE_SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE contact_entities (
    id INTEGER PRIMARY KEY
);

CREATE TABLE contact_points (
    id INTEGER PRIMARY KEY
);

CREATE TABLE provenance_records (
    id INTEGER PRIMARY KEY
);
"""


class ConnectionsSchemaTests(unittest.TestCase):

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(BASE_SCHEMA)

        self.db.execute(
            "INSERT INTO contact_entities(id) VALUES (1)"
        )
        self.db.execute(
            "INSERT INTO contact_entities(id) VALUES (2)"
        )

        self.db.execute(
            "INSERT INTO contact_points(id) VALUES (10)"
        )

        self.db.execute(
            "INSERT INTO provenance_records(id) VALUES (20)"
        )

        migrate(self.db)

    def tearDown(self):
        self.db.close()

    def test_migration_is_idempotent(self):
        migrate(self.db)

        names = {
            row[0]
            for row in self.db.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                """
            )
        }

        self.assertIn(
            "contact_relationships",
            names,
        )

        self.assertIn(
            "relationship_evidence",
            names,
        )

    def test_entity_to_entity_relationship(self):
        self.db.execute(
            """
            INSERT INTO contact_relationships(
                left_entity_id,
                right_entity_id,
                relationship_type,
                confidence,
                directionality
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                1,
                2,
                "associated_with",
                "document_sourced",
                "undirected",
            ),
        )

        row = self.db.execute(
            """
            SELECT
                left_entity_id,
                right_entity_id,
                relationship_type,
                confidence,
                directionality
            FROM contact_relationships
            """
        ).fetchone()

        self.assertEqual(
            row,
            (
                1,
                2,
                "associated_with",
                "document_sourced",
                "undirected",
            ),
        )

    def test_entity_to_point_relationship(self):
        self.db.execute(
            """
            INSERT INTO contact_relationships(
                left_entity_id,
                right_contact_point_id,
                relationship_type,
                confidence
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                1,
                10,
                "uses",
                "confirmed",
            ),
        )

        self.assertEqual(
            self.db.execute(
                """
                SELECT COUNT(*)
                FROM contact_relationships
                """
            ).fetchone()[0],
            1,
        )

    def test_endpoint_must_be_exactly_one_subject(self):
        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            self.db.execute(
                """
                INSERT INTO contact_relationships(
                    left_entity_id,
                    left_contact_point_id,
                    right_entity_id,
                    relationship_type
                )
                VALUES (1, 10, 2, 'invalid')
                """
            )

    def test_relationship_evidence(self):
        cur = self.db.execute(
            """
            INSERT INTO contact_relationships(
                left_entity_id,
                right_entity_id,
                relationship_type,
                confidence
            )
            VALUES (1, 2, 'vendor_of', 'document_sourced')
            """
        )

        relationship_id = cur.lastrowid

        self.db.execute(
            """
            INSERT INTO relationship_evidence(
                relationship_id,
                provenance_id,
                evidence_role,
                evidence_summary
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                relationship_id,
                20,
                "supporting",
                "Test provenance",
            ),
        )

        self.assertEqual(
            self.db.execute(
                """
                SELECT COUNT(*)
                FROM relationship_evidence
                """
            ).fetchone()[0],
            1,
        )

    def test_foreign_keys_enforced(self):
        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            self.db.execute(
                """
                INSERT INTO contact_relationships(
                    left_entity_id,
                    right_entity_id,
                    relationship_type
                )
                VALUES (1, 999, 'associated_with')
                """
            )


if __name__ == "__main__":
    unittest.main()


class ConnectionsHardeningTests(unittest.TestCase):

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute(
            "PRAGMA foreign_keys=ON"
        )

        self.db.executescript(
            BASE_SCHEMA
        )

        self.db.executemany(
            """
            INSERT INTO contact_entities(id)
            VALUES (?)
            """,
            [(1,), (2,), (3,)],
        )

        self.db.execute(
            """
            INSERT INTO contact_points(id)
            VALUES (10)
            """
        )

        migrate(self.db)

        from tools.unified_contacts.schema_connections import (
    harden_relationship_constraints,
            harden,
        )

        harden(self.db)

    def tearDown(self):
        self.db.close()

    def test_duplicate_active_relationship_blocked(self):
        values = (
            1,
            2,
            "vendor_of",
            "document_sourced",
            "directed",
        )

        sql = """
            INSERT INTO contact_relationships(
                left_entity_id,
                right_entity_id,
                relationship_type,
                confidence,
                directionality
            )
            VALUES (?, ?, ?, ?, ?)
        """

        self.db.execute(
            sql,
            values,
        )

        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            self.db.execute(
                sql,
                values,
            )

    def test_superseded_history_can_coexist(self):
        self.db.execute(
            """
            INSERT INTO contact_relationships(
                left_entity_id,
                right_entity_id,
                relationship_type,
                confidence,
                lifecycle_status,
                directionality
            )
            VALUES (
                1,
                2,
                'vendor_of',
                'document_sourced',
                'superseded',
                'directed'
            )
            """
        )

        self.db.execute(
            """
            INSERT INTO contact_relationships(
                left_entity_id,
                right_entity_id,
                relationship_type,
                confidence,
                lifecycle_status,
                directionality
            )
            VALUES (
                1,
                2,
                'vendor_of',
                'document_sourced',
                'active',
                'directed'
            )
            """
        )

        self.assertEqual(
            self.db.execute(
                """
                SELECT COUNT(*)
                FROM contact_relationships
                """
            ).fetchone()[0],
            2,
        )

    def test_different_relationship_type_allowed(self):
        for relationship_type in (
            "vendor_of",
            "associated_with",
        ):
            self.db.execute(
                """
                INSERT INTO contact_relationships(
                    left_entity_id,
                    right_entity_id,
                    relationship_type,
                    confidence,
                    directionality
                )
                VALUES (
                    1,
                    2,
                    ?,
                    'document_sourced',
                    'directed'
                )
                """,
                (relationship_type,),
            )

        self.assertEqual(
            self.db.execute(
                """
                SELECT COUNT(*)
                FROM contact_relationships
                """
            ).fetchone()[0],
            2,
        )

    def test_entity_point_duplicate_blocked(self):
        sql = """
            INSERT INTO contact_relationships(
                left_entity_id,
                right_contact_point_id,
                relationship_type,
                confidence,
                directionality
            )
            VALUES (
                1,
                10,
                'associated_with',
                'probable',
                'undirected'
            )
        """

        self.db.execute(sql)

        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            self.db.execute(sql)


class ConnectionsDatabaseHardeningTests(unittest.TestCase):

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys=ON")

        self.db.executescript(
            """
            CREATE TABLE contact_entities (
                id INTEGER PRIMARY KEY
            );

            CREATE TABLE contact_points (
                id INTEGER PRIMARY KEY
            );
            """
        )

        self.db.executemany(
            "INSERT INTO contact_entities(id) VALUES (?)",
            [(1,), (2,)],
        )

        self.db.executemany(
            "INSERT INTO contact_points(id) VALUES (?)",
            [(1,), (2,)],
        )

        migrate(self.db)
        harden_relationship_constraints(self.db)

    def tearDown(self):
        self.db.close()

    def insert_relationship(
        self,
        *,
        left_entity=None,
        right_entity=None,
        left_point=None,
        right_point=None,
        directionality="undirected",
        relationship_type="associated_with",
    ):
        return self.db.execute(
            """
            INSERT INTO contact_relationships(
                left_entity_id,
                right_entity_id,
                left_contact_point_id,
                right_contact_point_id,
                relationship_type,
                confidence,
                lifecycle_status,
                directionality
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                left_entity,
                right_entity,
                left_point,
                right_point,
                relationship_type,
                "document_sourced",
                "active",
                directionality,
            ),
        )

    def test_entity_self_edge_blocked(self):
        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "self-edge",
        ):
            self.insert_relationship(
                left_entity=1,
                right_entity=1,
            )

    def test_point_self_edge_blocked(self):
        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "self-edge",
        ):
            self.insert_relationship(
                left_point=1,
                right_point=1,
            )

    def test_canonical_entity_pair_allowed(self):
        self.insert_relationship(
            left_entity=1,
            right_entity=2,
        )

    def test_reversed_entity_pair_blocked(self):
        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "noncanonical",
        ):
            self.insert_relationship(
                left_entity=2,
                right_entity=1,
            )

    def test_entity_before_point_allowed(self):
        self.insert_relationship(
            left_entity=2,
            right_point=1,
        )

    def test_point_before_entity_blocked(self):
        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "noncanonical",
        ):
            self.insert_relationship(
                left_point=1,
                right_entity=2,
            )

    def test_numeric_namespace_overlap_allowed(self):
        self.insert_relationship(
            left_entity=1,
            right_point=1,
        )

    def test_directed_reverse_allowed(self):
        self.insert_relationship(
            left_entity=2,
            right_entity=1,
            directionality="directed",
            relationship_type="vendor_of",
        )

    def test_update_to_self_edge_blocked(self):
        cur = self.insert_relationship(
            left_entity=1,
            right_entity=2,
        )

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "self-edge",
        ):
            self.db.execute(
                """
                UPDATE contact_relationships
                SET right_entity_id=1
                WHERE id=?
                """,
                (cur.lastrowid,),
            )

    def test_update_to_noncanonical_blocked(self):
        cur = self.insert_relationship(
            left_entity=1,
            right_entity=2,
        )

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "noncanonical",
        ):
            self.db.execute(
                """
                UPDATE contact_relationships
                SET
                    left_entity_id=2,
                    right_entity_id=1
                WHERE id=?
                """,
                (cur.lastrowid,),
            )
