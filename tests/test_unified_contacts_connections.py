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
    id INTEGER PRIMARY KEY
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
            INSERT INTO provenance_records(id)
            VALUES (20)
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
                evidence_document_sourced=True,
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
            evidence_document_sourced=True,
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
            evidence_document_sourced=True,
            evidence_summary="test",
        )

        second = promote_candidate(
            self.db,
            candidate_id,
            20,
            evidence_document_sourced=True,
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


if __name__ == "__main__":
    unittest.main()
