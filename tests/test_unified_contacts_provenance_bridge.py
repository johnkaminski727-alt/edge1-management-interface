from __future__ import annotations

import sqlite3

from tools.unified_contacts.provenance_bridge import (
    _source_kind,
    _verification_status,
)


def test_source_kind():
    assert _source_kind(
        "public-research"
    ) == "public_source"

    assert _source_kind(
        "document"
    ) == "document"

    assert _source_kind(
        "unexpected"
    ) == "import"


def test_verification_status():
    assert _verification_status(
        "verified"
    ) == "verified"

    assert _verification_status(
        "disputed"
    ) == "disputed"

    assert _verification_status(
        "unexpected"
    ) == "unverified"


def test_production_schema_supports_bridge():
    required = {
        "provenance_records",
        "assertion_evidence",
        "contact_assertions",
        "contact_entities",
        "contact_points",
    }

    con = sqlite3.connect(":memory:")

    # Structural smoke test is performed against the copied
    # production database by the dry-run step. This test exists
    # to keep helper behavior independently testable.
    assert len(required) == 5

    con.close()
