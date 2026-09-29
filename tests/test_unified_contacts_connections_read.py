#!/usr/bin/env python3

import os
import sqlite3
import tempfile
import unittest

from server.unified_contacts import UnifiedContacts


SCHEMA = """
CREATE TABLE contact_entities (
    id INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    display_name TEXT,
    lifecycle_status TEXT NOT NULL,
    verification_status TEXT NOT NULL
);

CREATE TABLE contact_points (
    id INTEGER PRIMARY KEY,
    point_type TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    display_value TEXT,
    lifecycle_status TEXT NOT NULL
);

CREATE TABLE provenance_records (
    id INTEGER PRIMARY KEY,
    source_document_id INTEGER,
    source_kind TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_reference TEXT,
    source_page TEXT,
    source_url TEXT,
    source_sha256 TEXT,
    extraction_method TEXT,
    verification_status TEXT NOT NULL,
    notes TEXT,
    created_at TEXT
);

CREATE TABLE contact_relationships (
    id INTEGER PRIMARY KEY,
    left_entity_id INTEGER,
    right_entity_id INTEGER,
    left_contact_point_id INTEGER,
    right_contact_point_id INTEGER,
    relationship_type TEXT NOT NULL,
    confidence TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL,
    directionality TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE relationship_evidence (
    id INTEGER PRIMARY KEY,
    relationship_id INTEGER NOT NULL,
    provenance_id INTEGER NOT NULL,
    evidence_role TEXT NOT NULL,
    evidence_summary TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE candidate_correlations (
    id INTEGER PRIMARY KEY,
    left_entity_id INTEGER,
    right_entity_id INTEGER,
    left_contact_point_id INTEGER,
    right_contact_point_id INTEGER,
    correlation_type TEXT NOT NULL,
    confidence TEXT NOT NULL,
    review_status TEXT NOT NULL,
    rationale TEXT,
    created_at TEXT NOT NULL,
    reviewed_at TEXT
);
"""


class ConnectionsReadModelTests(unittest.TestCase):

    def setUp(self):
        handle = tempfile.NamedTemporaryFile(
            suffix=".sqlite",
            delete=False,
        )
        handle.close()
        self.path = handle.name

        db = sqlite3.connect(self.path)

        try:
            db.executescript(SCHEMA)

            db.executemany(
                """
                INSERT INTO contact_entities(
                    id,
                    entity_type,
                    canonical_name,
                    display_name,
                    lifecycle_status,
                    verification_status
                )
                VALUES (?, ?, ?, ?, 'active', ?)
                """,
                [
                    (
                        1,
                        "person",
                        "Example Person",
                        "Example Person",
                        "document_sourced",
                    ),
                    (
                        2,
                        "organization",
                        "Example Org",
                        "Example Org",
                        "document_sourced",
                    ),
                    (
                        3,
                        "organization",
                        "Other Org",
                        "Other Org",
                        "verified",
                    ),
                ],
            )

            db.execute(
                """
                INSERT INTO contact_points(
                    id,
                    point_type,
                    normalized_value,
                    display_value,
                    lifecycle_status
                )
                VALUES (
                    10,
                    'email',
                    'person@example.test',
                    'person@example.test',
                    'active'
                )
                """
            )

            db.execute(
                """
                INSERT INTO provenance_records(
                    id,
                    source_kind,
                    source_name,
                    source_reference,
                    extraction_method,
                    verification_status,
                    created_at
                )
                VALUES (
                    20,
                    'register',
                    'Example Registry',
                    'registry/example',
                    'test',
                    'document_sourced',
                    '2026-09-29 00:00:00'
                )
                """
            )

            db.executemany(
                """
                INSERT INTO contact_relationships(
                    id,
                    left_entity_id,
                    right_entity_id,
                    left_contact_point_id,
                    right_contact_point_id,
                    relationship_type,
                    confidence,
                    lifecycle_status,
                    directionality,
                    notes,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    '2026-09-29 00:00:00',
                    '2026-09-29 00:00:00'
                )
                """,
                [
                    (
                        30,
                        1,
                        2,
                        None,
                        None,
                        "works_for",
                        "document_sourced",
                        "active",
                        "directed",
                        "documented relationship",
                    ),
                    (
                        31,
                        2,
                        None,
                        None,
                        10,
                        "associated_with",
                        "probable",
                        "active",
                        "undirected",
                        "entity-point context",
                    ),
                    (
                        32,
                        2,
                        3,
                        None,
                        None,
                        "vendor_of",
                        "document_sourced",
                        "superseded",
                        "directed",
                        "historical relationship",
                    ),
                ],
            )

            db.execute(
                """
                INSERT INTO relationship_evidence(
                    id,
                    relationship_id,
                    provenance_id,
                    evidence_role,
                    evidence_summary,
                    created_at
                )
                VALUES (
                    40,
                    30,
                    20,
                    'supporting',
                    'Registry supports works_for',
                    '2026-09-29 00:00:00'
                )
                """
            )

            db.executemany(
                """
                INSERT INTO candidate_correlations(
                    id,
                    left_entity_id,
                    right_entity_id,
                    left_contact_point_id,
                    right_contact_point_id,
                    correlation_type,
                    confidence,
                    review_status,
                    rationale,
                    created_at,
                    reviewed_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    '2026-09-29 00:00:00',
                    ?
                )
                """,
                [
                    (
                        50,
                        1,
                        3,
                        None,
                        None,
                        "possible_match",
                        "possible",
                        "pending",
                        "review only",
                        None,
                    ),
                    (
                        51,
                        1,
                        None,
                        None,
                        10,
                        "associated_with",
                        "probable",
                        "accepted",
                        "accepted example",
                        "2026-09-29 00:10:00",
                    ),
                ],
            )

            db.commit()

        finally:
            db.close()

        self.store = UnifiedContacts(self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_relationships_default_active_only(self):
        rows = self.store.relationships()

        self.assertEqual(
            [row["relationship_id"] for row in rows],
            [31, 30],
        )

    def test_relationships_entity_filter_both_sides(self):
        rows = self.store.relationships(
            entity_id=1,
        )

        self.assertEqual(
            [row["relationship_id"] for row in rows],
            [30],
        )

        self.assertEqual(
            rows[0]["left_display_name"],
            "Example Person",
        )

        self.assertEqual(
            rows[0]["right_display_name"],
            "Example Org",
        )

    def test_relationships_point_endpoint_display(self):
        rows = self.store.relationships(
            contact_point_id=10,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["relationship_id"],
            31,
        )
        self.assertEqual(
            rows[0]["right_point_type"],
            "email",
        )
        self.assertEqual(
            rows[0]["right_normalized_value"],
            "person@example.test",
        )

    def test_relationships_can_request_history(self):
        rows = self.store.relationships(
            lifecycle_status="superseded",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["relationship_id"],
            32,
        )

    def test_relationship_evidence_is_separate(self):
        rows = self.store.relationship_evidence(30)

        self.assertEqual(len(rows), 1)

        row = rows[0]

        self.assertEqual(
            row["source_name"],
            "Example Registry",
        )
        self.assertEqual(
            row["verification_status"],
            "document_sourced",
        )
        self.assertEqual(
            row["evidence_summary"],
            "Registry supports works_for",
        )

    def test_relationship_evidence_unknown_is_empty(self):
        self.assertEqual(
            self.store.relationship_evidence(999),
            [],
        )

    def test_correlations_default_pending_only(self):
        rows = self.store.correlations()

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["correlation_id"],
            50,
        )
        self.assertEqual(
            rows[0]["correlation_type"],
            "possible_match",
        )

    def test_correlations_can_request_accepted(self):
        rows = self.store.correlations(
            review_status="accepted",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["correlation_id"],
            51,
        )
        self.assertEqual(
            rows[0]["right_point_type"],
            "email",
        )

    def test_correlations_entity_filter(self):
        rows = self.store.correlations(
            entity_id=3,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["correlation_id"],
            50,
        )

    def test_correlations_point_filter(self):
        rows = self.store.correlations(
            review_status="accepted",
            contact_point_id=10,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["correlation_id"],
            51,
        )


if __name__ == "__main__":
    unittest.main()
