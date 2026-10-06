from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from server.unified_contacts_merge import (
    ContactMergeError,
    UnifiedContactsMerge,
)


SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE contact_entities (
    id INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    display_name TEXT,
    lifecycle_status TEXT NOT NULL DEFAULT 'active',
    verification_status TEXT NOT NULL DEFAULT 'unverified',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE contact_points (
    id INTEGER PRIMARY KEY,
    point_type TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    display_value TEXT,
    lifecycle_status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE provenance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_kind TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_reference TEXT,
    extraction_method TEXT,
    verification_status TEXT NOT NULL DEFAULT 'unverified',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE contact_assertions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL
        REFERENCES contact_entities(id)
        ON DELETE CASCADE,
    contact_point_id INTEGER NOT NULL
        REFERENCES contact_points(id)
        ON DELETE CASCADE,
    assertion_type TEXT NOT NULL DEFAULT 'contact',
    confidence TEXT NOT NULL DEFAULT 'unverified',
    valid_from TEXT,
    valid_to TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(
        entity_id,
        contact_point_id,
        assertion_type
    )
);

CREATE TABLE assertion_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assertion_id INTEGER NOT NULL
        REFERENCES contact_assertions(id)
        ON DELETE CASCADE,
    provenance_id INTEGER NOT NULL
        REFERENCES provenance_records(id)
        ON DELETE CASCADE,
    evidence_role TEXT NOT NULL DEFAULT 'supports',
    evidence_summary TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE contact_entity_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL
        REFERENCES contact_entities(id)
        ON DELETE CASCADE,
    alias_name TEXT NOT NULL,
    alias_type TEXT NOT NULL DEFAULT 'alternate',
    confidence TEXT NOT NULL DEFAULT 'unverified',
    provenance_id INTEGER
        REFERENCES provenance_records(id)
        ON DELETE SET NULL,
    source_path TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(
        entity_id,
        alias_name,
        alias_type,
        provenance_id,
        source_path
    )
);

CREATE TABLE contact_attestations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER
        REFERENCES contact_entities(id)
        ON DELETE CASCADE,
    contact_point_id INTEGER
        REFERENCES contact_points(id)
        ON DELETE CASCADE,
    provenance_id INTEGER NOT NULL
        REFERENCES provenance_records(id)
        ON DELETE CASCADE,
    attribute TEXT NOT NULL,
    attested_value TEXT NOT NULL,
    classification TEXT,
    verification_status TEXT NOT NULL DEFAULT 'unverified',
    source_path TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(
        (
            entity_id IS NOT NULL
            AND contact_point_id IS NULL
        )
        OR
        (
            entity_id IS NULL
            AND contact_point_id IS NOT NULL
        )
    )
);

CREATE TABLE contact_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    left_entity_id INTEGER
        REFERENCES contact_entities(id)
        ON DELETE CASCADE,
    right_entity_id INTEGER
        REFERENCES contact_entities(id)
        ON DELETE CASCADE,
    left_contact_point_id INTEGER
        REFERENCES contact_points(id)
        ON DELETE CASCADE,
    right_contact_point_id INTEGER
        REFERENCES contact_points(id)
        ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'unverified',
    lifecycle_status TEXT NOT NULL DEFAULT 'active',
    directionality TEXT NOT NULL DEFAULT 'directed',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX
uq_contact_relationships_active_identity
ON contact_relationships (
    COALESCE(left_entity_id, -1),
    COALESCE(right_entity_id, -1),
    COALESCE(left_contact_point_id, -1),
    COALESCE(right_contact_point_id, -1),
    relationship_type
)
WHERE lifecycle_status='active';

CREATE TABLE candidate_correlations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    left_entity_id INTEGER
        REFERENCES contact_entities(id)
        ON DELETE CASCADE,
    right_entity_id INTEGER
        REFERENCES contact_entities(id)
        ON DELETE CASCADE,
    left_contact_point_id INTEGER
        REFERENCES contact_points(id)
        ON DELETE CASCADE,
    right_contact_point_id INTEGER
        REFERENCES contact_points(id)
        ON DELETE CASCADE,
    correlation_type TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'unverified',
    review_status TEXT NOT NULL DEFAULT 'pending',
    rationale TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT
);

CREATE TABLE contact_entity_merges (
    id INTEGER PRIMARY KEY,
    absorbed_entity_id INTEGER NOT NULL
        REFERENCES contact_entities(id),
    survivor_entity_id INTEGER NOT NULL
        REFERENCES contact_entities(id),
    provenance_id INTEGER
        REFERENCES provenance_records(id)
        ON DELETE SET NULL,
    reason TEXT NOT NULL,
    merged_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(
        absorbed_entity_id <> survivor_entity_id
    ),
    UNIQUE(absorbed_entity_id)
);
"""


class UnifiedContactsMergeTests(unittest.TestCase):

    def setUp(self):
        handle = tempfile.NamedTemporaryFile(
            suffix=".sqlite",
            delete=False,
        )
        handle.close()

        self.path = handle.name

        con = sqlite3.connect(self.path)

        try:
            con.executescript(SCHEMA)

            for point_id in (
                101,
                102,
                103,
                104,
            ):
                con.execute(
                    """
                    INSERT INTO contact_points (
                        id,
                        point_type,
                        normalized_value,
                        display_value,
                        lifecycle_status
                    )
                    VALUES (
                        ?,
                        'phone',
                        ?,
                        ?,
                        'active'
                    )
                    """,
                    (
                        point_id,
                        f"+1306555{point_id:04d}",
                        f"306-555-{point_id:04d}",
                    ),
                )

            con.commit()

        finally:
            con.close()

        self.merge = UnifiedContactsMerge(
            self.path
        )

    def tearDown(self):
        os.unlink(self.path)

    def connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def add_entity(
        self,
        entity_id,
        canonical,
        display=None,
    ):
        con = self.connect()

        try:
            con.execute(
                """
                INSERT INTO contact_entities (
                    id,
                    entity_type,
                    canonical_name,
                    display_name,
                    lifecycle_status,
                    verification_status
                )
                VALUES (
                    ?,
                    'person',
                    ?,
                    ?,
                    'active',
                    'unverified'
                )
                """,
                (
                    entity_id,
                    canonical,
                    display,
                ),
            )

            con.commit()
        finally:
            con.close()

    def add_provenance(self, reference):
        con = self.connect()

        try:
            cur = con.execute(
                """
                INSERT INTO provenance_records (
                    source_kind,
                    source_name,
                    source_reference,
                    extraction_method,
                    verification_status
                )
                VALUES (
                    'manual',
                    'Merge test',
                    ?,
                    'manual_operator',
                    'unverified'
                )
                """,
                (reference,),
            )

            con.commit()
            return int(cur.lastrowid)

        finally:
            con.close()

    def add_assertion(
        self,
        entity_id,
        point_id,
        *,
        valid_from=None,
        valid_to=None,
        notes=None,
    ):
        con = self.connect()

        try:
            cur = con.execute(
                """
                INSERT INTO contact_assertions (
                    entity_id,
                    contact_point_id,
                    assertion_type,
                    confidence,
                    valid_from,
                    valid_to,
                    notes
                )
                VALUES (
                    ?,
                    ?,
                    'contact',
                    'unverified',
                    ?,
                    ?,
                    ?
                )
                """,
                (
                    entity_id,
                    point_id,
                    valid_from,
                    valid_to,
                    notes,
                ),
            )

            con.commit()
            return int(cur.lastrowid)

        finally:
            con.close()

    def test_success_preserves_identity_history_and_dependencies(
        self,
    ):
        self.add_entity(
            1,
            "Survivor",
            "Survivor",
        )

        self.add_entity(
            2,
            "Absorbed Canonical",
            "Absorbed Display",
        )

        provenance_id = self.add_provenance(
            "fixture"
        )

        assertion_id = self.add_assertion(
            2,
            101,
            valid_from="2026-10-01 00:00:00",
            valid_to=None,
            notes="Current assertion.",
        )

        self.add_entity(
            3,
            "Relationship Target",
        )

        con = self.connect()

        try:
            con.execute(
                """
                INSERT INTO assertion_evidence (
                    assertion_id,
                    provenance_id,
                    evidence_role,
                    evidence_summary
                )
                VALUES (?, ?, 'supports', 'fixture')
                """,
                (
                    assertion_id,
                    provenance_id,
                ),
            )

            con.execute(
                """
                INSERT INTO contact_attestations (
                    entity_id,
                    provenance_id,
                    attribute,
                    attested_value,
                    classification,
                    verification_status,
                    source_path
                )
                VALUES (
                    2,
                    ?,
                    'canonical_name',
                    'Absorbed Canonical',
                    'manual_operator',
                    'unverified',
                    'edge1://test'
                )
                """,
                (provenance_id,),
            )

            con.execute(
                """
                INSERT INTO contact_relationships (
                    left_entity_id,
                    right_entity_id,
                    relationship_type
                )
                VALUES (
                    2,
                    3,
                    'fixture'
                )
                """
            )

            con.execute(
                """
                INSERT INTO candidate_correlations (
                    left_entity_id,
                    right_entity_id,
                    correlation_type
                )
                VALUES (
                    3,
                    2,
                    'fixture'
                )
                """
            )

            con.commit()

        finally:
            con.close()

        result = self.merge.merge(
            1,
            2,
            merged_by="unit-test-actor",
        )

        self.assertEqual(
            result.assertions_moved,
            1,
        )
        self.assertEqual(
            result.aliases_preserved,
            2,
        )
        self.assertEqual(
            result.attestations_moved,
            0,
        )
        self.assertEqual(
            result.relationships_repointed,
            1,
        )
        self.assertEqual(
            result.correlations_repointed,
            1,
        )

        con = self.connect()

        try:
            absorbed = con.execute(
                """
                SELECT lifecycle_status
                FROM contact_entities
                WHERE id=2
                """
            ).fetchone()

            self.assertEqual(
                absorbed["lifecycle_status"],
                "retired",
            )

            aliases = con.execute(
                """
                SELECT
                    alias_name,
                    provenance_id,
                    source_path
                FROM contact_entity_aliases
                WHERE entity_id=1
                  AND alias_type='former_name'
                ORDER BY alias_name
                """
            ).fetchall()

            self.assertEqual(
                {
                    row["alias_name"]
                    for row in aliases
                },
                {
                    "Absorbed Canonical",
                    "Absorbed Display",
                },
            )

            self.assertTrue(
                all(
                    row["provenance_id"]
                    is not None
                    for row in aliases
                )
            )

            self.assertTrue(
                all(
                    row["source_path"]
                    == "edge1://contacts/merge"
                    for row in aliases
                )
            )

            moved = con.execute(
                """
                SELECT *
                FROM contact_assertions
                WHERE id=?
                """,
                (assertion_id,),
            ).fetchone()

            self.assertEqual(
                moved["entity_id"],
                1,
            )

            self.assertEqual(
                moved["valid_from"],
                "2026-10-01 00:00:00",
            )

            self.assertIsNone(
                moved["valid_to"]
            )

            attestation = con.execute(
                """
                SELECT entity_id
                FROM contact_attestations
                WHERE provenance_id=?
                """,
                (provenance_id,),
            ).fetchone()

            self.assertEqual(
                attestation["entity_id"],
                2,
            )

            relationship = con.execute(
                """
                SELECT
                    left_entity_id,
                    right_entity_id
                FROM contact_relationships
                WHERE relationship_type='fixture'
                """
            ).fetchone()

            self.assertEqual(
                (
                    relationship["left_entity_id"],
                    relationship["right_entity_id"],
                ),
                (1, 3),
            )

            correlation = con.execute(
                """
                SELECT
                    left_entity_id,
                    right_entity_id
                FROM candidate_correlations
                WHERE correlation_type='fixture'
                """
            ).fetchone()

            self.assertEqual(
                (
                    correlation["left_entity_id"],
                    correlation["right_entity_id"],
                ),
                (3, 1),
            )

            ledger = con.execute(
                """
                SELECT *
                FROM contact_entity_merges
                WHERE absorbed_entity_id=2
                """
            ).fetchone()

            self.assertEqual(
                ledger["survivor_entity_id"],
                1,
            )

            self.assertEqual(
                ledger["merged_by"],
                "unit-test-actor",
            )

            self.assertFalse(
                con.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
            )

        finally:
            con.close()

    def test_temporal_collision_rolls_back_everything(
        self,
    ):
        self.add_entity(
            10,
            "Temporal Survivor",
        )
        self.add_entity(
            11,
            "Temporal Absorbed",
            "Temporal Former",
        )

        self.add_assertion(
            10,
            102,
            valid_from="2026-10-01",
            valid_to=None,
            notes="Current",
        )

        self.add_assertion(
            11,
            102,
            valid_from="2026-09-01",
            valid_to="2026-09-30",
            notes="Historical",
        )

        con = self.connect()

        try:
            provenance_before = con.execute(
                """
                SELECT COUNT(*)
                FROM provenance_records
                """
            ).fetchone()[0]
        finally:
            con.close()

        with self.assertRaises(
            ContactMergeError
        ):
            self.merge.merge(
                10,
                11,
                merged_by="unit-test",
            )

        con = self.connect()

        try:
            entity = con.execute(
                """
                SELECT lifecycle_status
                FROM contact_entities
                WHERE id=11
                """
            ).fetchone()

            self.assertEqual(
                entity["lifecycle_status"],
                "active",
            )

            self.assertEqual(
                con.execute(
                    """
                    SELECT COUNT(*)
                    FROM contact_entity_aliases
                    WHERE entity_id=10
                    """
                ).fetchone()[0],
                0,
            )

            self.assertEqual(
                con.execute(
                    """
                    SELECT COUNT(*)
                    FROM contact_entity_merges
                    WHERE absorbed_entity_id=11
                    """
                ).fetchone()[0],
                0,
            )

            self.assertEqual(
                con.execute(
                    """
                    SELECT COUNT(*)
                    FROM provenance_records
                    """
                ).fetchone()[0],
                provenance_before,
            )

        finally:
            con.close()

    def test_direct_relationship_rejected(
        self,
    ):
        self.add_entity(20, "Left")
        self.add_entity(21, "Right")

        con = self.connect()

        try:
            con.execute(
                """
                INSERT INTO contact_relationships (
                    left_entity_id,
                    right_entity_id,
                    relationship_type
                )
                VALUES (
                    20,
                    21,
                    'direct'
                )
                """
            )
            con.commit()
        finally:
            con.close()

        with self.assertRaises(
            ContactMergeError
        ):
            self.merge.merge(
                20,
                21,
                merged_by="unit-test",
            )

    def test_direct_correlation_rejected(
        self,
    ):
        self.add_entity(30, "Left")
        self.add_entity(31, "Right")

        con = self.connect()

        try:
            con.execute(
                """
                INSERT INTO candidate_correlations (
                    left_entity_id,
                    right_entity_id,
                    correlation_type
                )
                VALUES (
                    31,
                    30,
                    'direct'
                )
                """
            )
            con.commit()
        finally:
            con.close()

        with self.assertRaises(
            ContactMergeError
        ):
            self.merge.merge(
                30,
                31,
                merged_by="unit-test",
            )

    def test_relationship_collision_rolls_back(
        self,
    ):
        self.add_entity(40, "Survivor")
        self.add_entity(41, "Absorbed")
        self.add_entity(42, "Target")

        con = self.connect()

        try:
            for left in (
                40,
                41,
            ):
                con.execute(
                    """
                    INSERT INTO contact_relationships (
                        left_entity_id,
                        right_entity_id,
                        relationship_type
                    )
                    VALUES (
                        ?,
                        42,
                        'collision'
                    )
                    """,
                    (left,),
                )

            con.commit()
        finally:
            con.close()

        with self.assertRaises(
            ContactMergeError
        ):
            self.merge.merge(
                40,
                41,
                merged_by="unit-test",
            )

        con = self.connect()

        try:
            rows = con.execute(
                """
                SELECT left_entity_id
                FROM contact_relationships
                WHERE right_entity_id=42
                  AND relationship_type='collision'
                ORDER BY left_entity_id
                """
            ).fetchall()

            self.assertEqual(
                [
                    row["left_entity_id"]
                    for row in rows
                ],
                [40, 41],
            )

            absorbed = con.execute(
                """
                SELECT lifecycle_status
                FROM contact_entities
                WHERE id=41
                """
            ).fetchone()

            self.assertEqual(
                absorbed["lifecycle_status"],
                "active",
            )

        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
