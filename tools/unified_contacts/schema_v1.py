#!/usr/bin/env python3
"""Additive Unified Contacts schema for Edge1.

Design rules:
- canonical identity is separate from evidence/provenance
- contact points are independently asserted
- observations do not establish identity
- uncertain correlations do not merge entities
- Connections Web remains a separate relationship layer
"""

from __future__ import annotations

import sqlite3


SCHEMA_VERSION = "unified-contacts-1"


DDL = r"""
CREATE TABLE IF NOT EXISTS contact_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    entity_type TEXT NOT NULL
        CHECK(entity_type IN ('person', 'organization')),

    canonical_name TEXT NOT NULL,
    display_name TEXT,

    lifecycle_status TEXT NOT NULL DEFAULT 'active'
        CHECK(lifecycle_status IN (
            'active',
            'inactive',
            'unknown',
            'retired'
        )),

    verification_status TEXT NOT NULL DEFAULT 'unverified'
        CHECK(verification_status IN (
            'verified',
            'document_sourced',
            'unverified',
            'disputed'
        )),

    legacy_organization_id INTEGER
        REFERENCES organizations(id) ON DELETE SET NULL,

    notes TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS
    idx_contact_entities_legacy_org
ON contact_entities(legacy_organization_id)
WHERE legacy_organization_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS
    idx_contact_entities_name
ON contact_entities(canonical_name);

CREATE INDEX IF NOT EXISTS
    idx_contact_entities_type
ON contact_entities(entity_type);


CREATE TABLE IF NOT EXISTS contact_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    point_type TEXT NOT NULL
        CHECK(point_type IN (
            'phone',
            'fax',
            'email',
            'website',
            'domain',
            'postal_address'
        )),

    normalized_value TEXT NOT NULL,
    display_value TEXT,

    classification TEXT,

    lifecycle_status TEXT NOT NULL DEFAULT 'active'
        CHECK(lifecycle_status IN (
            'active',
            'inactive',
            'unknown',
            'retired'
        )),

    legacy_phone_number_id INTEGER
        REFERENCES phone_numbers(id) ON DELETE SET NULL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(point_type, normalized_value)
);

CREATE UNIQUE INDEX IF NOT EXISTS
    idx_contact_points_legacy_phone
ON contact_points(legacy_phone_number_id)
WHERE legacy_phone_number_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS
    idx_contact_points_type
ON contact_points(point_type);


CREATE TABLE IF NOT EXISTS contact_assertions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    entity_id INTEGER NOT NULL
        REFERENCES contact_entities(id) ON DELETE CASCADE,

    contact_point_id INTEGER NOT NULL
        REFERENCES contact_points(id) ON DELETE CASCADE,

    assertion_type TEXT NOT NULL DEFAULT 'contact'
        CHECK(assertion_type IN (
            'contact',
            'business',
            'personal',
            'support',
            'billing',
            'fax',
            'mailing',
            'physical',
            'other'
        )),

    confidence TEXT NOT NULL DEFAULT 'unverified'
        CHECK(confidence IN (
            'confirmed',
            'document_sourced',
            'probable',
            'unverified',
            'disputed'
        )),

    valid_from TEXT,
    valid_to TEXT,
    notes TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(entity_id, contact_point_id, assertion_type)
);

CREATE INDEX IF NOT EXISTS
    idx_contact_assertions_entity
ON contact_assertions(entity_id);

CREATE INDEX IF NOT EXISTS
    idx_contact_assertions_point
ON contact_assertions(contact_point_id);


CREATE TABLE IF NOT EXISTS provenance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source_document_id INTEGER
        REFERENCES source_documents(id) ON DELETE SET NULL,

    source_kind TEXT NOT NULL
        CHECK(source_kind IN (
            'document',
            'register',
            'email',
            'manual',
            'public_source',
            'import',
            'system'
        )),

    source_name TEXT NOT NULL,
    source_reference TEXT,
    source_page TEXT,
    source_url TEXT,
    source_sha256 TEXT,

    extraction_method TEXT,

    verification_status TEXT NOT NULL DEFAULT 'unverified'
        CHECK(verification_status IN (
            'verified',
            'document_sourced',
            'unverified',
            'superseded',
            'disputed',
            'missing_source'
        )),

    notes TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS
    idx_provenance_source_document
ON provenance_records(source_document_id);


CREATE TABLE IF NOT EXISTS assertion_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    assertion_id INTEGER NOT NULL
        REFERENCES contact_assertions(id) ON DELETE CASCADE,

    provenance_id INTEGER NOT NULL
        REFERENCES provenance_records(id) ON DELETE CASCADE,

    evidence_role TEXT NOT NULL DEFAULT 'supports'
        CHECK(evidence_role IN (
            'supports',
            'contradicts',
            'supersedes',
            'context_only'
        )),

    evidence_summary TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(assertion_id, provenance_id, evidence_role)
);


CREATE TABLE IF NOT EXISTS contact_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    contact_point_id INTEGER
        REFERENCES contact_points(id) ON DELETE SET NULL,

    provenance_id INTEGER
        REFERENCES provenance_records(id) ON DELETE SET NULL,

    observation_type TEXT NOT NULL
        CHECK(observation_type IN (
            'call',
            'message',
            'document_occurrence',
            'email_occurrence',
            'import_occurrence',
            'other'
        )),

    observed_value TEXT,
    occurred_at TEXT,
    direction TEXT,

    classification TEXT NOT NULL DEFAULT 'unknown'
        CHECK(classification IN (
            'unknown',
            'normal',
            'suspected_spam',
            'suspected_scam',
            'telemarketing',
            'spoofing_suspected',
            'noise',
            'other'
        )),

    confidence TEXT NOT NULL DEFAULT 'unverified'
        CHECK(confidence IN (
            'confirmed',
            'probable',
            'unverified',
            'disputed'
        )),

    notes TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS
    idx_contact_observations_point
ON contact_observations(contact_point_id);

CREATE INDEX IF NOT EXISTS
    idx_contact_observations_classification
ON contact_observations(classification);


CREATE TABLE IF NOT EXISTS candidate_correlations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    left_entity_id INTEGER
        REFERENCES contact_entities(id) ON DELETE CASCADE,

    right_entity_id INTEGER
        REFERENCES contact_entities(id) ON DELETE CASCADE,

    left_contact_point_id INTEGER
        REFERENCES contact_points(id) ON DELETE CASCADE,

    right_contact_point_id INTEGER
        REFERENCES contact_points(id) ON DELETE CASCADE,

    correlation_type TEXT NOT NULL,

    confidence TEXT NOT NULL DEFAULT 'unverified'
        CHECK(confidence IN (
            'probable',
            'possible',
            'unverified',
            'disputed'
        )),

    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK(review_status IN (
            'pending',
            'accepted',
            'rejected',
            'superseded'
        )),

    rationale TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT,

    CHECK(
        left_entity_id IS NOT NULL OR
        left_contact_point_id IS NOT NULL
    ),

    CHECK(
        right_entity_id IS NOT NULL OR
        right_contact_point_id IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS
    idx_candidate_correlations_review
ON candidate_correlations(review_status);


CREATE TABLE IF NOT EXISTS rejected_extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    provenance_id INTEGER
        REFERENCES provenance_records(id) ON DELETE SET NULL,

    raw_value TEXT NOT NULL,

    candidate_type TEXT,

    rejection_reason TEXT NOT NULL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


INSERT OR IGNORE INTO schema_metadata(key, value)
VALUES ('unified_contacts_schema_version', 'unified-contacts-1');
"""


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(DDL)
