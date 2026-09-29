import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "unified_contacts"
sys.path.insert(0, str(TOOLS))

from schema_v1 import migrate


LEGACY = """
CREATE TABLE organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE phone_numbers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized_number TEXT NOT NULL UNIQUE
);

CREATE TABLE source_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_type TEXT NOT NULL,
    source_name TEXT NOT NULL
);

CREATE TABLE schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def database():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(LEGACY)
    return conn


def test_schema_is_additive():
    conn = database()

    conn.execute(
        "INSERT INTO organizations(name) VALUES (?)",
        ("Existing Organization",),
    )
    conn.execute(
        "INSERT INTO phone_numbers(normalized_number) VALUES (?)",
        ("+13065550100",),
    )

    migrate(conn)

    assert conn.execute(
        "SELECT COUNT(*) FROM organizations"
    ).fetchone()[0] == 1

    assert conn.execute(
        "SELECT COUNT(*) FROM phone_numbers"
    ).fetchone()[0] == 1

    assert conn.execute(
        "PRAGMA foreign_key_check"
    ).fetchall() == []


def test_observation_does_not_require_entity():
    conn = database()
    migrate(conn)

    point = conn.execute(
        """
        INSERT INTO contact_points(
            point_type,
            normalized_value,
            display_value
        )
        VALUES ('phone', '+13065550101', '(306) 555-0101')
        """
    ).lastrowid

    conn.execute(
        """
        INSERT INTO contact_observations(
            contact_point_id,
            observation_type,
            classification,
            confidence
        )
        VALUES (?, 'call', 'suspected_spam', 'unverified')
        """,
        (point,),
    )

    assert conn.execute(
        "SELECT COUNT(*) FROM contact_entities"
    ).fetchone()[0] == 0

    assert conn.execute(
        "SELECT COUNT(*) FROM contact_assertions"
    ).fetchone()[0] == 0


def test_identity_requires_explicit_assertion():
    conn = database()
    migrate(conn)

    entity = conn.execute(
        """
        INSERT INTO contact_entities(
            entity_type,
            canonical_name,
            verification_status
        )
        VALUES ('organization', 'Example Corp', 'verified')
        """
    ).lastrowid

    point = conn.execute(
        """
        INSERT INTO contact_points(
            point_type,
            normalized_value
        )
        VALUES ('email', 'support@example.test')
        """
    ).lastrowid

    assert conn.execute(
        "SELECT COUNT(*) FROM contact_assertions"
    ).fetchone()[0] == 0

    conn.execute(
        """
        INSERT INTO contact_assertions(
            entity_id,
            contact_point_id,
            confidence
        )
        VALUES (?, ?, 'confirmed')
        """,
        (entity, point),
    )

    assert conn.execute(
        "SELECT COUNT(*) FROM contact_assertions"
    ).fetchone()[0] == 1


def test_candidate_correlation_does_not_merge():
    conn = database()
    migrate(conn)

    left = conn.execute(
        """
        INSERT INTO contact_entities(
            entity_type,
            canonical_name
        )
        VALUES ('organization', 'Alpha')
        """
    ).lastrowid

    right = conn.execute(
        """
        INSERT INTO contact_entities(
            entity_type,
            canonical_name
        )
        VALUES ('organization', 'Alpha Services')
        """
    ).lastrowid

    conn.execute(
        """
        INSERT INTO candidate_correlations(
            left_entity_id,
            right_entity_id,
            correlation_type,
            confidence,
            rationale
        )
        VALUES (?, ?, 'possible_duplicate', 'possible', ?)
        """,
        (left, right, "Similar names only"),
    )

    assert conn.execute(
        "SELECT COUNT(*) FROM contact_entities"
    ).fetchone()[0] == 2

    assert conn.execute(
        """
        SELECT review_status
        FROM candidate_correlations
        """
    ).fetchone()[0] == "pending"


def test_rejected_numeric_noise_is_preserved():
    conn = database()
    migrate(conn)

    conn.execute(
        """
        INSERT INTO rejected_extractions(
            raw_value,
            candidate_type,
            rejection_reason
        )
        VALUES ('9039163944', 'phone', 'ambiguous numeric token')
        """
    )

    assert conn.execute(
        "SELECT COUNT(*) FROM rejected_extractions"
    ).fetchone()[0] == 1

    assert conn.execute(
        "SELECT COUNT(*) FROM contact_points"
    ).fetchone()[0] == 0


def test_schema_migration_is_idempotent():
    conn = database()

    migrate(conn)
    migrate(conn)

    version = conn.execute(
        """
        SELECT value
        FROM schema_metadata
        WHERE key='unified_contacts_schema_version'
        """
    ).fetchone()[0]

    assert version == "unified-contacts-1"
    assert conn.execute(
        "PRAGMA foreign_key_check"
    ).fetchall() == []


def test_unresolved_legacy_phone_does_not_create_identity_assertion():
    from legacy_bridge import bridge_legacy

    conn = database()

    conn.executescript("""
        CREATE TABLE associations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number_id INTEGER NOT NULL,
            organization_id INTEGER,
            association_label TEXT,
            confidence TEXT NOT NULL,
            research_notes TEXT
        );
    """)

    org = conn.execute(
        "INSERT INTO organizations(name) VALUES ('Example Org')"
    ).lastrowid

    phone = conn.execute(
        """
        INSERT INTO phone_numbers(normalized_number)
        VALUES ('+13065550111')
        """
    ).lastrowid

    conn.execute("""
        ALTER TABLE phone_numbers
        ADD COLUMN display_number TEXT
    """)

    conn.execute("""
        ALTER TABLE phone_numbers
        ADD COLUMN status TEXT DEFAULT 'unresolved'
    """)

    conn.execute("""
        INSERT INTO associations(
            phone_number_id,
            organization_id,
            confidence
        )
        VALUES (?, ?, 'unresolved')
    """, (phone, org))

    migrate(conn)
    stats = bridge_legacy(conn)

    assert stats["unresolved_skipped"] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM contact_points"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM contact_entities"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM contact_assertions"
    ).fetchone()[0] == 0


def test_confirmed_legacy_association_creates_explicit_assertion():
    from legacy_bridge import bridge_legacy

    conn = database()

    conn.executescript("""
        CREATE TABLE associations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number_id INTEGER NOT NULL,
            organization_id INTEGER,
            association_label TEXT,
            confidence TEXT NOT NULL,
            research_notes TEXT
        );

        ALTER TABLE phone_numbers
        ADD COLUMN display_number TEXT;

        ALTER TABLE phone_numbers
        ADD COLUMN status TEXT DEFAULT 'unresolved';
    """)

    org = conn.execute(
        "INSERT INTO organizations(name) VALUES ('Confirmed Org')"
    ).lastrowid

    phone = conn.execute(
        """
        INSERT INTO phone_numbers(
            normalized_number,
            display_number,
            status
        )
        VALUES (
            '+13065550112',
            '(306) 555-0112',
            'confirmed'
        )
        """
    ).lastrowid

    conn.execute("""
        INSERT INTO associations(
            phone_number_id,
            organization_id,
            association_label,
            confidence,
            research_notes
        )
        VALUES (?, ?, 'Confirmed Org', 'confirmed', 'verified')
    """, (phone, org))

    migrate(conn)
    stats = bridge_legacy(conn)

    assert stats["confirmed_assertions"] == 1

    row = conn.execute("""
        SELECT a.confidence, e.canonical_name, p.normalized_value
        FROM contact_assertions AS a
        JOIN contact_entities AS e
          ON e.id = a.entity_id
        JOIN contact_points AS p
          ON p.id = a.contact_point_id
    """).fetchone()

    assert row == (
        "confirmed",
        "Confirmed Org",
        "+13065550112",
    )
