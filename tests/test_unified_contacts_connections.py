import sqlite3
import unittest

from tools.unified_contacts.connections import (
    accept_candidate,
    promote_candidate,
    reject_candidate,
)

from tools.unified_contacts.schema_connections import (
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
    id INTEGER PRIMARY KEY,
    verification_status TEXT NOT NULL
);

CREATE TABLE candidate_correlations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    left_entity_id INTEGER
        REFERENCES contact_entities(id),

    right_entity_id INTEGER
        REFERENCES contact_entities(id),

    left_contact_point_id INTEGER
        REFERENCES contact_points(id),

    right_contact_point_id INTEGER
        REFERENCES contact_points(id),

    correlation_type TEXT NOT NULL,

    confidence TEXT NOT NULL,

    review_status TEXT NOT NULL
        DEFAULT 'pending',

    rationale TEXT,

    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    reviewed_at TEXT
);
"""


class ConnectionsLifecycleTests(unittest.TestCase):

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
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

        self.db.execute(
            """
            INSERT INTO provenance_records(
                id,
                verification_status
            )
            VALUES (20, 'document_sourced')
            """
        )

        migrate(self.db)

    def tearDown(self):
        self.db.close()

    def candidate(
        self,
        relationship_type="vendor_of",
        confidence="probable",
        status="pending",
    ):
        cur = self.db.execute(
            """
            INSERT INTO candidate_correlations(
                left_entity_id,
                right_entity_id,
                correlation_type,
                confidence,
                review_status,
                rationale
            )
            VALUES (1, 2, ?, ?, ?, ?)
            """,
            (
                relationship_type,
                confidence,
                status,
                "test candidate",
            ),
        )

        return cur.lastrowid

    def test_pending_cannot_promote(self):
        candidate_id = self.candidate()

        with self.assertRaises(ValueError):
            promote_candidate(
                self.db,
                candidate_id,
                20,
            )

    def test_accept_then_promote(self):
        candidate_id = self.candidate()

        accept_candidate(
            self.db,
            candidate_id,
        )

        result = promote_candidate(
            self.db,
            candidate_id,
            20,
            evidence_summary="test",
        )

        self.assertTrue(
            result.relationship_created
        )

        self.assertTrue(
            result.evidence_created
        )

        row = self.db.execute(
            """
            SELECT *
            FROM contact_relationships
            WHERE id=?
            """,
            (result.relationship_id,),
        ).fetchone()

        self.assertEqual(
            row["relationship_type"],
            "vendor_of",
        )

        self.assertEqual(
            row["confidence"],
            "document_sourced",
        )

        self.assertEqual(
            row["directionality"],
            "directed",
        )

    def test_promotion_is_idempotent(self):
        candidate_id = self.candidate()

        accept_candidate(
            self.db,
            candidate_id,
        )

        first = promote_candidate(
            self.db,
            candidate_id,
            20,
            evidence_summary="test",
        )

        second = promote_candidate(
            self.db,
            candidate_id,
            20,
            evidence_summary="test",
        )

        self.assertEqual(
            first.relationship_id,
            second.relationship_id,
        )

        self.assertTrue(
            first.relationship_created
        )

        self.assertFalse(
            second.relationship_created
        )

        self.assertTrue(
            first.evidence_created
        )

        self.assertFalse(
            second.evidence_created
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

        self.assertEqual(
            self.db.execute(
                """
                SELECT COUNT(*)
                FROM relationship_evidence
                """
            ).fetchone()[0],
            1,
        )

    def test_accept_is_idempotent(self):
        candidate_id = self.candidate()

        accept_candidate(
            self.db,
            candidate_id,
        )

        accept_candidate(
            self.db,
            candidate_id,
        )

        status = self.db.execute(
            """
            SELECT review_status
            FROM candidate_correlations
            WHERE id=?
            """,
            (candidate_id,),
        ).fetchone()[0]

        self.assertEqual(
            status,
            "accepted",
        )

    def test_reject_is_idempotent(self):
        candidate_id = self.candidate()

        reject_candidate(
            self.db,
            candidate_id,
        )

        reject_candidate(
            self.db,
            candidate_id,
        )

        status = self.db.execute(
            """
            SELECT review_status
            FROM candidate_correlations
            WHERE id=?
            """,
            (candidate_id,),
        ).fetchone()[0]

        self.assertEqual(
            status,
            "rejected",
        )

    def test_rejected_cannot_accept(self):
        candidate_id = self.candidate()

        reject_candidate(
            self.db,
            candidate_id,
        )

        with self.assertRaises(ValueError):
            accept_candidate(
                self.db,
                candidate_id,
            )

    def test_accepted_cannot_reject(self):
        candidate_id = self.candidate()

        accept_candidate(
            self.db,
            candidate_id,
        )

        with self.assertRaises(ValueError):
            reject_candidate(
                self.db,
                candidate_id,
            )

    def test_possible_match_cannot_promote(self):
        candidate_id = self.candidate(
            relationship_type="possible_match",
            confidence="possible",
        )

        accept_candidate(
            self.db,
            candidate_id,
        )

        with self.assertRaises(ValueError):
            promote_candidate(
                self.db,
                candidate_id,
                20,
            )

    def test_missing_provenance_rejected(self):
        candidate_id = self.candidate()

        accept_candidate(
            self.db,
            candidate_id,
        )

        with self.assertRaises(ValueError):
            promote_candidate(
                self.db,
                candidate_id,
                999,
            )

    def test_entity_to_point_candidate(self):
        cur = self.db.execute(
            """
            INSERT INTO candidate_correlations(
                left_entity_id,
                right_contact_point_id,
                correlation_type,
                confidence,
                review_status
            )
            VALUES (
                1,
                10,
                'associated_with',
                'probable',
                'pending'
            )
            """
        )

        candidate_id = cur.lastrowid

        accept_candidate(
            self.db,
            candidate_id,
        )

        result = promote_candidate(
            self.db,
            candidate_id,
            20,
        )

        row = self.db.execute(
            """
            SELECT
                left_entity_id,
                right_contact_point_id
            FROM contact_relationships
            WHERE id=?
            """,
            (result.relationship_id,),
        ).fetchone()

        self.assertEqual(
            tuple(row),
            (1, 10),
        )


class ConnectionsMutationSafetyTests(unittest.TestCase):

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(BASE_SCHEMA)

        self.db.executemany(
            "INSERT INTO contact_entities(id) VALUES (?)",
            [(1,), (2,), (3,)],
        )

        self.db.executemany(
            "INSERT INTO contact_points(id) VALUES (?)",
            [(1,), (10,)],
        )

        self.db.executemany(
            """
            INSERT INTO provenance_records(
                id,
                verification_status
            )
            VALUES (?, ?)
            """,
            [
                (20, "verified"),
                (21, "document_sourced"),
                (22, "missing_source"),
                (23, "unverified"),
            ],
        )

        migrate(self.db)

    def candidate(
        self,
        *,
        left_entity=None,
        right_entity=None,
        left_point=None,
        right_point=None,
        relationship_type="associated_with",
        confidence="probable",
    ):
        cur = self.db.execute(
            """
            INSERT INTO candidate_correlations(
                left_entity_id,
                right_entity_id,
                left_contact_point_id,
                right_contact_point_id,
                correlation_type,
                confidence,
                review_status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                left_entity,
                right_entity,
                left_point,
                right_point,
                relationship_type,
                confidence,
            ),
        )

        candidate_id = cur.lastrowid

        accept_candidate(
            self.db,
            candidate_id,
        )

        return candidate_id

    def relationship_confidence(self, relationship_id):
        return self.db.execute(
            """
            SELECT confidence
            FROM contact_relationships
            WHERE id=?
            """,
            (relationship_id,),
        ).fetchone()[0]

    def test_verified_provenance_confirms(self):
        candidate_id = self.candidate(
            left_entity=1,
            right_entity=2,
            confidence="possible",
        )

        result = promote_candidate(
            self.db,
            candidate_id,
            20,
        )

        self.assertEqual(
            self.relationship_confidence(
                result.relationship_id
            ),
            "confirmed",
        )

    def test_document_sourced_provenance(self):
        candidate_id = self.candidate(
            left_entity=1,
            right_entity=2,
            confidence="possible",
        )

        result = promote_candidate(
            self.db,
            candidate_id,
            21,
        )

        self.assertEqual(
            self.relationship_confidence(
                result.relationship_id
            ),
            "document_sourced",
        )

    def test_unverified_cannot_inflate(self):
        candidate_id = self.candidate(
            left_entity=1,
            right_entity=2,
            confidence="possible",
        )

        result = promote_candidate(
            self.db,
            candidate_id,
            23,
        )

        self.assertEqual(
            self.relationship_confidence(
                result.relationship_id
            ),
            "unverified",
        )

    def test_missing_source_preserves_probable(self):
        candidate_id = self.candidate(
            left_entity=1,
            right_entity=2,
            confidence="probable",
        )

        result = promote_candidate(
            self.db,
            candidate_id,
            22,
        )

        self.assertEqual(
            self.relationship_confidence(
                result.relationship_id
            ),
            "probable",
        )

    def test_entity_self_edge_rejected(self):
        candidate_id = self.candidate(
            left_entity=1,
            right_entity=1,
        )

        with self.assertRaisesRegex(
            ValueError,
            "self-relationships",
        ):
            promote_candidate(
                self.db,
                candidate_id,
                21,
            )

        count = self.db.execute(
            """
            SELECT COUNT(*)
            FROM contact_relationships
            """
        ).fetchone()[0]

        self.assertEqual(count, 0)

    def test_point_self_edge_rejected(self):
        candidate_id = self.candidate(
            left_point=10,
            right_point=10,
        )

        with self.assertRaisesRegex(
            ValueError,
            "self-relationships",
        ):
            promote_candidate(
                self.db,
                candidate_id,
                21,
            )

    def test_numeric_namespace_overlap_not_self(self):
        candidate_id = self.candidate(
            left_entity=1,
            right_point=1,
        )

        result = promote_candidate(
            self.db,
            candidate_id,
            21,
        )

        self.assertTrue(
            result.relationship_created
        )

    def test_undirected_reverse_collapses(self):
        first_id = self.candidate(
            left_entity=2,
            right_entity=1,
            relationship_type="associated_with",
        )

        first = promote_candidate(
            self.db,
            first_id,
            21,
        )

        second_id = self.candidate(
            left_entity=1,
            right_entity=2,
            relationship_type="associated_with",
        )

        second = promote_candidate(
            self.db,
            second_id,
            21,
        )

        self.assertEqual(
            first.relationship_id,
            second.relationship_id,
        )

        self.assertTrue(
            first.relationship_created
        )
        self.assertFalse(
            second.relationship_created
        )

        row = self.db.execute(
            """
            SELECT
                left_entity_id,
                right_entity_id
            FROM contact_relationships
            WHERE id=?
            """,
            (first.relationship_id,),
        ).fetchone()

        self.assertEqual(
            tuple(row),
            (1, 2),
        )

    def test_directed_reverse_remains_distinct(self):
        first_id = self.candidate(
            left_entity=1,
            right_entity=2,
            relationship_type="vendor_of",
        )

        second_id = self.candidate(
            left_entity=2,
            right_entity=1,
            relationship_type="vendor_of",
        )

        first = promote_candidate(
            self.db,
            first_id,
            21,
        )

        second = promote_candidate(
            self.db,
            second_id,
            21,
        )

        self.assertNotEqual(
            first.relationship_id,
            second.relationship_id,
        )


if __name__ == "__main__":
    unittest.main()
