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
    lifecycle_status TEXT NOT NULL,
    legacy_phone_number_id INTEGER
);

CREATE TABLE contact_assertions (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER NOT NULL,
    contact_point_id INTEGER NOT NULL,
    assertion_type TEXT NOT NULL,
    confidence TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY(entity_id)
        REFERENCES contact_entities(id),
    FOREIGN KEY(contact_point_id)
        REFERENCES contact_points(id)
);

CREATE TABLE provenance_records (
    id INTEGER PRIMARY KEY,
    source_document_id INTEGER,
    source_kind TEXT NOT NULL,
    source_name TEXT,
    source_reference TEXT,
    source_page TEXT,
    source_url TEXT,
    source_sha256 TEXT,
    extraction_method TEXT,
    verification_status TEXT NOT NULL,
    notes TEXT,
    created_at TEXT
);

CREATE TABLE assertion_evidence (
    id INTEGER PRIMARY KEY,
    assertion_id INTEGER NOT NULL,
    provenance_id INTEGER NOT NULL,
    evidence_role TEXT NOT NULL,
    evidence_summary TEXT,
    created_at TEXT,
    FOREIGN KEY(assertion_id)
        REFERENCES contact_assertions(id),
    FOREIGN KEY(provenance_id)
        REFERENCES provenance_records(id)
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
    notes TEXT,
    created_at TEXT,
    FOREIGN KEY(contact_point_id)
        REFERENCES contact_points(id),
    FOREIGN KEY(provenance_id)
        REFERENCES provenance_records(id)
);

CREATE TABLE contact_entity_aliases (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER NOT NULL,
    alias_name TEXT NOT NULL,
    alias_type TEXT NOT NULL,
    confidence TEXT NOT NULL,
    provenance_id INTEGER,
    source_path TEXT,
    notes TEXT,
    FOREIGN KEY(entity_id)
        REFERENCES contact_entities(id),
    FOREIGN KEY(provenance_id)
        REFERENCES provenance_records(id)
);

CREATE TABLE contact_attestations (
    id INTEGER PRIMARY KEY,
    entity_id INTEGER,
    contact_point_id INTEGER,
    provenance_id INTEGER NOT NULL,
    attribute TEXT NOT NULL,
    attested_value TEXT NOT NULL,
    classification TEXT,
    verification_status TEXT NOT NULL,
    source_path TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY(entity_id)
        REFERENCES contact_entities(id),
    FOREIGN KEY(contact_point_id)
        REFERENCES contact_points(id),
    FOREIGN KEY(provenance_id)
        REFERENCES provenance_records(id)
);

CREATE TABLE candidate_correlations (
    id INTEGER PRIMARY KEY
);

CREATE TABLE phone_numbers (
    id INTEGER PRIMARY KEY,
    status TEXT,
    occurrence_count INTEGER
);
"""


class UnifiedContactsReadApiTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(
            suffix=".sqlite",
            delete=False,
        )
        handle.close()

        self.path = handle.name

        con = sqlite3.connect(self.path)

        try:
            con.execute("PRAGMA foreign_keys=ON")
            con.executescript(SCHEMA)

            con.execute("""
                INSERT INTO contact_entities (
                    id,
                    entity_type,
                    canonical_name,
                    display_name,
                    lifecycle_status,
                    verification_status
                )
                VALUES (
                    1,
                    'organization',
                    'Example Org',
                    'Example Org',
                    'active',
                    'verified'
                )
            """)

            con.execute("""
                INSERT INTO contact_points (
                    id,
                    point_type,
                    normalized_value,
                    display_value,
                    lifecycle_status
                )
                VALUES (
                    1,
                    'phone',
                    '+13065550100',
                    '306-555-0100',
                    'active'
                )
            """)

            con.execute("""
                INSERT INTO contact_points (
                    id,
                    point_type,
                    normalized_value,
                    display_value,
                    lifecycle_status
                )
                VALUES (
                    2,
                    'phone',
                    '+13065550101',
                    '306-555-0101',
                    'active'
                )
            """)

            con.execute("""
                INSERT INTO contact_points (
                    id,
                    point_type,
                    normalized_value,
                    display_value,
                    lifecycle_status
                )
                VALUES (
                    3,
                    'domain',
                    'example.test',
                    'example.test',
                    'active'
                )
            """)

            con.execute("""
                INSERT INTO contact_assertions (
                    id,
                    entity_id,
                    contact_point_id,
                    assertion_type,
                    confidence
                )
                VALUES (
                    1,
                    1,
                    1,
                    'uses',
                    'confirmed'
                )
            """)

            con.execute("""
                INSERT INTO contact_assertions (
                    id,
                    entity_id,
                    contact_point_id,
                    assertion_type,
                    confidence
                )
                VALUES (
                    2,
                    1,
                    3,
                    'uses',
                    'document_sourced'
                )
            """)

            con.execute("""
                INSERT INTO provenance_records (
                    id,
                    source_kind,
                    source_name,
                    source_reference,
                    extraction_method,
                    verification_status
                )
                VALUES (
                    1,
                    'public_source',
                    'Example Public Source',
                    'public-ref',
                    'test',
                    'verified'
                )
            """)

            con.execute("""
                INSERT INTO assertion_evidence (
                    id,
                    assertion_id,
                    provenance_id,
                    evidence_role,
                    evidence_summary
                )
                VALUES (
                    1,
                    1,
                    1,
                    'supports',
                    'Supports identity assertion'
                )
            """)

            con.execute("""
                INSERT INTO provenance_records (
                    id,
                    source_kind,
                    source_name,
                    source_reference,
                    extraction_method,
                    verification_status
                )
                VALUES (
                    2,
                    'document',
                    'Example Bill',
                    'bill-ref',
                    'test',
                    'document_sourced'
                )
            """)

            con.execute("""
                INSERT INTO contact_observations (
                    id,
                    contact_point_id,
                    provenance_id,
                    observation_type,
                    observed_value,
                    classification,
                    confidence
                )
                VALUES (
                    1,
                    1,
                    2,
                    'document_occurrence',
                    '306-555-0100',
                    'unknown',
                    'unverified'
                )
            """)

            con.execute("""
                INSERT INTO contact_observations (
                    id,
                    contact_point_id,
                    provenance_id,
                    observation_type,
                    observed_value,
                    classification,
                    confidence
                )
                VALUES (
                    2,
                    2,
                    2,
                    'document_occurrence',
                    '306-555-0101',
                    'unknown',
                    'unverified'
                )
            """)

            con.execute("""
                INSERT INTO contact_entity_aliases (
                    id,
                    entity_id,
                    alias_name,
                    alias_type,
                    confidence,
                    provenance_id,
                    source_path
                )
                VALUES (
                    1,
                    1,
                    'Example Operating Name',
                    'operating_name',
                    'document_sourced',
                    1,
                    '$.example.alias'
                )
            """)

            con.execute("""
                INSERT INTO contact_attestations (
                    id,
                    entity_id,
                    provenance_id,
                    attribute,
                    attested_value,
                    classification,
                    verification_status,
                    source_path
                )
                VALUES (
                    1,
                    1,
                    1,
                    'identity_name',
                    'Example Org',
                    'source_named_organization',
                    'document_sourced',
                    '$.example.name'
                )
            """)

            con.execute("""
                INSERT INTO contact_attestations (
                    id,
                    contact_point_id,
                    provenance_id,
                    attribute,
                    attested_value,
                    classification,
                    verification_status,
                    source_path
                )
                VALUES (
                    2,
                    1,
                    1,
                    'phone_classification',
                    'test',
                    'test',
                    'unverified',
                    '$.example.phone'
                )
            """)

            con.commit()

        finally:
            con.close()

        self.store = UnifiedContacts(self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_summary_uses_true_unassigned_count(self):
        summary = self.store.summary()

        self.assertEqual(summary["entities"], 1)
        self.assertEqual(summary["contact_points"], 3)
        self.assertEqual(summary["assertions"], 2)
        self.assertEqual(summary["domains"], 1)
        self.assertEqual(summary["unassigned_phones"], 1)

        # This proves we count contact points with no assertion
        # rather than relying on points - assertion row count.
        self.assertEqual(summary["unassigned"], 1)

        self.assertEqual(summary["provenance"], 2)
        self.assertEqual(summary["observations"], 2)

    def test_sources_are_provenance_records(self):
        rows = self.store.sources(limit=10)

        self.assertEqual(len(rows), 2)

        self.assertEqual(
            {row["source_kind"] for row in rows},
            {"public_source", "document"},
        )

        public = next(
            row
            for row in rows
            if row["source_kind"] == "public_source"
        )

        document = next(
            row
            for row in rows
            if row["source_kind"] == "document"
        )

        self.assertEqual(public["assertion_links"], 1)
        self.assertEqual(public["observation_links"], 0)

        self.assertEqual(document["assertion_links"], 0)
        self.assertEqual(document["observation_links"], 2)

    def test_observation_remains_contextual(self):
        rows = self.store.observations(
            contact_point_id=1,
            limit=10,
        )

        self.assertEqual(len(rows), 1)

        row = rows[0]

        self.assertEqual(
            row["observation_type"],
            "document_occurrence",
        )

        self.assertEqual(
            row["classification"],
            "unknown",
        )

        self.assertEqual(
            row["confidence"],
            "unverified",
        )

        self.assertEqual(
            row["source_kind"],
            "document",
        )

    def test_evidence_keeps_layers_separate(self):
        result = self.store.evidence(
            contact_point_id=1,
            limit=10,
        )

        self.assertEqual(
            len(result["assertions"]),
            1,
        )

        self.assertEqual(
            len(result["assertion_evidence"]),
            1,
        )

        self.assertEqual(
            len(result["observations"]),
            1,
        )

        identity_evidence = (
            result["assertion_evidence"][0]
        )

        observation = result["observations"][0]

        self.assertEqual(
            identity_evidence["source_kind"],
            "public_source",
        )

        self.assertEqual(
            observation["source_kind"],
            "document",
        )

        self.assertEqual(
            observation["confidence"],
            "unverified",
        )

    def test_unassigned_point_can_have_observation(self):
        result = self.store.evidence(
            contact_point_id=2,
            limit=10,
        )

        self.assertEqual(
            result["assertions"],
            [],
        )

        self.assertEqual(
            result["assertion_evidence"],
            [],
        )

        self.assertEqual(
            len(result["observations"]),
            1,
        )


    def test_entities_are_one_row_per_entity(self):
        rows = self.store.entities(limit=10)

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["canonical_name"],
            "Example Org",
        )
        self.assertEqual(
            rows[0]["contact_point_count"],
            2,
        )
        self.assertEqual(
            rows[0]["alias_count"],
            1,
        )
        self.assertEqual(
            rows[0]["attestation_count"],
            1,
        )

    def test_entity_search_matches_alias(self):
        rows = self.store.entities(
            query="Operating Name",
            limit=10,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["canonical_name"],
            "Example Org",
        )

    def test_legacy_search_matches_alias(self):
        rows = self.store.search(
            query="Operating Name",
            limit=10,
        )

        self.assertEqual(len(rows), 2)

        self.assertEqual(
            {
                row["point_type"]
                for row in rows
            },
            {"phone", "domain"},
        )

        self.assertEqual(
            rows[0]["canonical_name"],
            "Example Org",
        )

    def test_entity_evidence_keeps_new_layers_separate(self):
        result = self.store.evidence(
            entity_id=1,
            limit=10,
        )

        self.assertEqual(
            len(result["assertions"]),
            2,
        )
        self.assertEqual(
            len(result["assertion_evidence"]),
            1,
        )
        self.assertEqual(
            len(result["aliases"]),
            1,
        )
        self.assertEqual(
            len(result["attestations"]),
            2,
        )
        self.assertEqual(
            len(result["observations"]),
            1,
        )

        statuses = {
            row["verification_status"]
            for row in result["attestations"]
        }

        self.assertEqual(
            statuses,
            {"document_sourced", "unverified"},
        )

    def test_evidence_requires_exactly_one_selector(self):
        with self.assertRaises(ValueError):
            self.store.evidence(limit=10)

        with self.assertRaises(ValueError):
            self.store.evidence(
                entity_id=1,
                contact_point_id=1,
                limit=10,
            )



    def test_domain_search_kind(self):
        rows = self.store.search(
            query="",
            kind="domains",
            limit=250,
        )

        self.assertEqual(len(rows), 1)

        self.assertEqual(
            rows[0]["point_type"],
            "domain",
        )

        self.assertEqual(
            rows[0]["normalized_value"],
            "example.test",
        )

        self.assertEqual(
            rows[0]["canonical_name"],
            "Example Org",
        )

if __name__ == "__main__":
    unittest.main()
