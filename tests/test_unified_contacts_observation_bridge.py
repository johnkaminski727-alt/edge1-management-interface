#!/usr/bin/env python3

import sqlite3
import unittest

from tools.unified_contacts.observation_bridge import (
    EXTRACTION_METHOD,
    _document_provenance,
    _verification_status,
    bridge_observations,
)


SCHEMA = """
CREATE TABLE source_documents (
    id INTEGER PRIMARY KEY,
    document_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_reference TEXT,
    sha256 TEXT,
    verification_status TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE contact_points (
    id INTEGER PRIMARY KEY,
    point_type TEXT NOT NULL,
    legacy_phone_number_id INTEGER
);

CREATE TABLE occurrences (
    id INTEGER PRIMARY KEY,
    phone_number_id INTEGER NOT NULL,
    source_document_id INTEGER NOT NULL,
    raw_value TEXT,
    notes TEXT
);

CREATE TABLE provenance_records (
    id INTEGER PRIMARY KEY,
    source_document_id INTEGER,
    source_kind TEXT NOT NULL,
    source_name TEXT,
    source_reference TEXT,
    source_sha256 TEXT,
    extraction_method TEXT,
    verification_status TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE contact_observations (
    id INTEGER PRIMARY KEY,
    contact_point_id INTEGER,
    provenance_id INTEGER,
    observation_type TEXT NOT NULL,
    observed_value TEXT,
    occurred_at TEXT,
    direction TEXT,
    classification TEXT NOT NULL,
    confidence TEXT NOT NULL,
    notes TEXT
);
"""


def fixture():
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)

    con.execute(
        """
        INSERT INTO source_documents (
            id,
            document_type,
            source_name,
            source_reference,
            verification_status
        )
        VALUES (1, 'bill', 'Example Bill', 'bill-1', 'recovered')
        """
    )

    con.execute(
        """
        INSERT INTO contact_points (
            id,
            point_type,
            legacy_phone_number_id
        )
        VALUES (1, 'phone', 1)
        """
    )

    return con


class VerificationMappingTests(unittest.TestCase):
    def test_recovered_document_mapping(self):
        self.assertEqual(
            _verification_status("recovered"),
            "document_sourced",
        )

    def test_missing_document_mapping(self):
        self.assertEqual(
            _verification_status("missing"),
            "missing_source",
        )

    def test_verified_document_mapping(self):
        self.assertEqual(
            _verification_status("verified"),
            "verified",
        )

    def test_partial_document_mapping(self):
        self.assertEqual(
            _verification_status("partial"),
            "unverified",
        )

    def test_unknown_document_mapping(self):
        self.assertEqual(
            _verification_status("unexpected"),
            "unverified",
        )


class ObservationBridgeHardeningTests(unittest.TestCase):
    def test_occurrence_one_does_not_match_ten(self):
        con = fixture()

        try:
            provenance_id, created = _document_provenance(
                con,
                1,
            )
            self.assertTrue(created)

            con.execute(
                """
                INSERT INTO contact_observations (
                    contact_point_id,
                    provenance_id,
                    observation_type,
                    observed_value,
                    classification,
                    confidence,
                    notes
                )
                VALUES (
                    1,
                    ?,
                    'document_occurrence',
                    '3065550100',
                    'unknown',
                    'unverified',
                    'legacy_occurrence_id=10;'
                )
                """,
                (provenance_id,),
            )

            con.execute(
                """
                INSERT INTO occurrences (
                    id,
                    phone_number_id,
                    source_document_id,
                    raw_value,
                    notes
                )
                VALUES (
                    1,
                    1,
                    1,
                    '3065550100',
                    'fixture'
                )
                """
            )

            stats = bridge_observations(con)

            self.assertEqual(
                stats["observations_created"],
                1,
            )

            rows = con.execute(
                """
                SELECT notes
                FROM contact_observations
                ORDER BY id
                """
            ).fetchall()

            self.assertEqual(len(rows), 2)

            self.assertTrue(
                any(
                    "legacy_occurrence_id=1;"
                    in (row[0] or "")
                    for row in rows
                )
            )

        finally:
            con.close()

    def test_duplicate_document_provenance_raises(self):
        con = fixture()

        try:
            for _ in range(2):
                con.execute(
                    """
                    INSERT INTO provenance_records (
                        source_document_id,
                        source_kind,
                        source_name,
                        extraction_method,
                        verification_status
                    )
                    VALUES (
                        1,
                        'document',
                        'Example Bill',
                        ?,
                        'document_sourced'
                    )
                    """,
                    (EXTRACTION_METHOD,),
                )

            with self.assertRaisesRegex(
                RuntimeError,
                "Duplicate document provenance",
            ):
                _document_provenance(con, 1)

        finally:
            con.close()

    def test_duplicate_observation_marker_raises(self):
        con = fixture()

        try:
            provenance_id, created = _document_provenance(
                con,
                1,
            )
            self.assertTrue(created)

            con.execute(
                """
                INSERT INTO occurrences (
                    id,
                    phone_number_id,
                    source_document_id,
                    raw_value,
                    notes
                )
                VALUES (
                    1,
                    1,
                    1,
                    '3065550100',
                    'fixture'
                )
                """
            )

            for _ in range(2):
                con.execute(
                    """
                    INSERT INTO contact_observations (
                        contact_point_id,
                        provenance_id,
                        observation_type,
                        observed_value,
                        classification,
                        confidence,
                        notes
                    )
                    VALUES (
                        1,
                        ?,
                        'document_occurrence',
                        '3065550100',
                        'unknown',
                        'unverified',
                        'legacy_occurrence_id=1;'
                    )
                    """,
                    (provenance_id,),
                )

            with self.assertRaisesRegex(
                RuntimeError,
                "Duplicate observation",
            ):
                bridge_observations(con)

        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
