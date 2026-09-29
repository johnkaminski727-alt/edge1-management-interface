import sqlite3


DDL = r"""
CREATE TABLE IF NOT EXISTS contact_relationships (
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

    confidence TEXT NOT NULL
        DEFAULT 'unverified'
        CHECK(confidence IN (
            'confirmed',
            'document_sourced',
            'probable',
            'possible',
            'unverified',
            'disputed'
        )),

    lifecycle_status TEXT NOT NULL
        DEFAULT 'active'
        CHECK(lifecycle_status IN (
            'active',
            'inactive',
            'superseded',
            'disputed'
        )),

    directionality TEXT NOT NULL
        DEFAULT 'directed'
        CHECK(directionality IN (
            'directed',
            'undirected'
        )),

    notes TEXT,

    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CHECK(
        left_entity_id IS NOT NULL OR
        left_contact_point_id IS NOT NULL
    ),

    CHECK(
        right_entity_id IS NOT NULL OR
        right_contact_point_id IS NOT NULL
    ),

    CHECK(
        NOT (
            left_entity_id IS NOT NULL AND
            left_contact_point_id IS NOT NULL
        )
    ),

    CHECK(
        NOT (
            right_entity_id IS NOT NULL AND
            right_contact_point_id IS NOT NULL
        )
    )
);


CREATE INDEX IF NOT EXISTS
    idx_contact_relationships_left_entity
ON contact_relationships(left_entity_id);


CREATE INDEX IF NOT EXISTS
    idx_contact_relationships_right_entity
ON contact_relationships(right_entity_id);


CREATE INDEX IF NOT EXISTS
    idx_contact_relationships_left_point
ON contact_relationships(left_contact_point_id);


CREATE INDEX IF NOT EXISTS
    idx_contact_relationships_right_point
ON contact_relationships(right_contact_point_id);


CREATE INDEX IF NOT EXISTS
    idx_contact_relationships_type
ON contact_relationships(relationship_type);


CREATE TABLE IF NOT EXISTS
relationship_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    relationship_id INTEGER NOT NULL
        REFERENCES contact_relationships(id)
        ON DELETE CASCADE,

    provenance_id INTEGER NOT NULL
        REFERENCES provenance_records(id)
        ON DELETE CASCADE,

    evidence_role TEXT NOT NULL
        DEFAULT 'supporting',

    evidence_summary TEXT,

    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(
        relationship_id,
        provenance_id,
        evidence_role
    )
);


CREATE INDEX IF NOT EXISTS
    idx_relationship_evidence_relationship
ON relationship_evidence(relationship_id);


CREATE INDEX IF NOT EXISTS
    idx_relationship_evidence_provenance
ON relationship_evidence(provenance_id);
"""


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(DDL)


HARDENING_DDL = r"""
CREATE UNIQUE INDEX IF NOT EXISTS
    uq_contact_relationships_active_identity
ON contact_relationships(
    COALESCE(left_entity_id, -1),
    COALESCE(left_contact_point_id, -1),
    COALESCE(right_entity_id, -1),
    COALESCE(right_contact_point_id, -1),
    relationship_type
)
WHERE lifecycle_status='active';
"""


def harden(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        "PRAGMA foreign_keys=ON"
    )
    connection.executescript(
        HARDENING_DDL
    )


def harden_relationship_constraints(db):
    """Install database-level relationship safety invariants."""

    db.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS
        trg_contact_relationships_no_self_insert
        BEFORE INSERT ON contact_relationships
        WHEN
            (
                NEW.left_entity_id IS NOT NULL
                AND NEW.right_entity_id IS NOT NULL
                AND NEW.left_entity_id = NEW.right_entity_id
            )
            OR
            (
                NEW.left_contact_point_id IS NOT NULL
                AND NEW.right_contact_point_id IS NOT NULL
                AND NEW.left_contact_point_id =
                    NEW.right_contact_point_id
            )
        BEGIN
            SELECT RAISE(
                ABORT,
                'contact relationship self-edge'
            );
        END;


        CREATE TRIGGER IF NOT EXISTS
        trg_contact_relationships_no_self_update
        BEFORE UPDATE ON contact_relationships
        WHEN
            (
                NEW.left_entity_id IS NOT NULL
                AND NEW.right_entity_id IS NOT NULL
                AND NEW.left_entity_id = NEW.right_entity_id
            )
            OR
            (
                NEW.left_contact_point_id IS NOT NULL
                AND NEW.right_contact_point_id IS NOT NULL
                AND NEW.left_contact_point_id =
                    NEW.right_contact_point_id
            )
        BEGIN
            SELECT RAISE(
                ABORT,
                'contact relationship self-edge'
            );
        END;


        CREATE TRIGGER IF NOT EXISTS
        trg_contact_relationships_canonical_insert
        BEFORE INSERT ON contact_relationships
        WHEN
            NEW.directionality = 'undirected'
            AND
            (
                CASE
                    WHEN NEW.left_entity_id IS NOT NULL
                        THEN 0
                    ELSE 1
                END
                >
                CASE
                    WHEN NEW.right_entity_id IS NOT NULL
                        THEN 0
                    ELSE 1
                END

                OR

                (
                    CASE
                        WHEN NEW.left_entity_id IS NOT NULL
                            THEN 0
                        ELSE 1
                    END
                    =
                    CASE
                        WHEN NEW.right_entity_id IS NOT NULL
                            THEN 0
                        ELSE 1
                    END

                    AND

                    COALESCE(
                        NEW.left_entity_id,
                        NEW.left_contact_point_id
                    )
                    >
                    COALESCE(
                        NEW.right_entity_id,
                        NEW.right_contact_point_id
                    )
                )
            )
        BEGIN
            SELECT RAISE(
                ABORT,
                'noncanonical undirected relationship'
            );
        END;


        CREATE TRIGGER IF NOT EXISTS
        trg_contact_relationships_canonical_update
        BEFORE UPDATE ON contact_relationships
        WHEN
            NEW.directionality = 'undirected'
            AND
            (
                CASE
                    WHEN NEW.left_entity_id IS NOT NULL
                        THEN 0
                    ELSE 1
                END
                >
                CASE
                    WHEN NEW.right_entity_id IS NOT NULL
                        THEN 0
                    ELSE 1
                END

                OR

                (
                    CASE
                        WHEN NEW.left_entity_id IS NOT NULL
                            THEN 0
                        ELSE 1
                    END
                    =
                    CASE
                        WHEN NEW.right_entity_id IS NOT NULL
                            THEN 0
                        ELSE 1
                    END

                    AND

                    COALESCE(
                        NEW.left_entity_id,
                        NEW.left_contact_point_id
                    )
                    >
                    COALESCE(
                        NEW.right_entity_id,
                        NEW.right_contact_point_id
                    )
                )
            )
        BEGIN
            SELECT RAISE(
                ABORT,
                'noncanonical undirected relationship'
            );
        END;
        """
    )
