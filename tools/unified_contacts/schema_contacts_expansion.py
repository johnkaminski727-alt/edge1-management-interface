"""Additive schema for richer Unified Contacts identity evidence.

This extension deliberately separates:
- canonical entity identity,
- entity aliases,
- source-specific attestations,
- provenance.

It is additive and idempotent.
"""

SCHEMA_VERSION = "unified-contacts-3g1"

DDL = """
CREATE TABLE IF NOT EXISTS contact_entity_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    entity_id INTEGER NOT NULL
        REFERENCES contact_entities(id) ON DELETE CASCADE,

    alias_name TEXT NOT NULL,

    alias_type TEXT NOT NULL DEFAULT 'alternate'
        CHECK(alias_type IN (
            'operating_name',
            'trade_name',
            'brand',
            'alternate',
            'former_name',
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

    provenance_id INTEGER
        REFERENCES provenance_records(id) ON DELETE SET NULL,

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

CREATE INDEX IF NOT EXISTS
    idx_contact_entity_aliases_entity
ON contact_entity_aliases(entity_id);

CREATE INDEX IF NOT EXISTS
    idx_contact_entity_aliases_name
ON contact_entity_aliases(alias_name);


CREATE TABLE IF NOT EXISTS contact_attestations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    entity_id INTEGER
        REFERENCES contact_entities(id) ON DELETE CASCADE,

    contact_point_id INTEGER
        REFERENCES contact_points(id) ON DELETE CASCADE,

    provenance_id INTEGER NOT NULL
        REFERENCES provenance_records(id) ON DELETE CASCADE,

    attribute TEXT NOT NULL,

    attested_value TEXT NOT NULL,

    classification TEXT,

    verification_status TEXT NOT NULL DEFAULT 'unverified'
        CHECK(verification_status IN (
            'verified',
            'document_sourced',
            'unverified',
            'superseded',
            'disputed',
            'missing_source'
        )),

    source_path TEXT NOT NULL,

    notes TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK(
        (entity_id IS NOT NULL AND contact_point_id IS NULL)
        OR
        (entity_id IS NULL AND contact_point_id IS NOT NULL)
    ),

    UNIQUE(
        entity_id,
        contact_point_id,
        provenance_id,
        attribute,
        attested_value,
        classification,
        source_path
    )
);

CREATE INDEX IF NOT EXISTS
    idx_contact_attestations_entity
ON contact_attestations(entity_id);

CREATE INDEX IF NOT EXISTS
    idx_contact_attestations_point
ON contact_attestations(contact_point_id);

CREATE INDEX IF NOT EXISTS
    idx_contact_attestations_provenance
ON contact_attestations(provenance_id);

CREATE INDEX IF NOT EXISTS
    idx_contact_attestations_attribute
ON contact_attestations(attribute);
"""


def apply_schema(connection):
    connection.executescript(DDL)
