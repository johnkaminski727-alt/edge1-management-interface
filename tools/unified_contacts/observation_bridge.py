"""Legacy occurrence -> Unified Contacts observation bridge.

Important semantics:

Legacy occurrences are workbook-level phone/document relationships.
They are NOT individual calls.

phone_numbers.occurrence_count retains the aggregate activity count.

The bridge therefore creates:

    source_document
        -> document provenance
        -> document_occurrence observation
        -> canonical phone contact point

No identity assertion is created.
No timestamp is inferred from a filename.
No individual call events are synthesized.
"""

from __future__ import annotations

import sqlite3


EXTRACTION_METHOD = "legacy_occurrence_document_bridge"

OBSERVATION_NOTE = (
    "Legacy workbook-level phone/source-document relationship. "
    "This observation does not represent an individual call and "
    "does not establish ownership or identity. Aggregate activity "
    "count remains on the legacy phone-number record."
)


def _verification_status(document_status: str) -> str:
    if document_status == "recovered":
        return "document_sourced"

    if document_status == "verified":
        return "verified"

    if document_status == "missing":
        return "missing_source"

    if document_status == "partial":
        return "unverified"

    return "unverified"


def _document_provenance(
    con: sqlite3.Connection,
    source_document_id: int,
) -> tuple[int, bool]:
    row = con.execute(
        """
        SELECT
            id,
            document_type,
            source_name,
            source_reference,
            sha256,
            verification_status,
            notes
        FROM source_documents
        WHERE id=?
        """,
        (source_document_id,),
    ).fetchone()

    if row is None:
        raise RuntimeError(
            f"Missing source document {source_document_id}"
        )

    (
        document_id,
        document_type,
        source_name,
        source_reference,
        sha256,
        verification_status,
        document_notes,
    ) = row

    existing = con.execute(
        """
        SELECT id
        FROM provenance_records
        WHERE source_document_id=?
          AND extraction_method=?
        ORDER BY id
        """,
        (
            document_id,
            EXTRACTION_METHOD,
        ),
    ).fetchall()

    if len(existing) > 1:
        raise RuntimeError(
            "Duplicate document provenance already exists "
            f"for source document {document_id}"
        )

    if existing:
        return existing[0][0], False

    status = _verification_status(
        verification_status
    )

    notes = (
        "Document provenance created from legacy "
        "Phone Intelligence source-document inventory. "
        f"Legacy document type: {document_type}. "
        f"Legacy recovery status: {verification_status}."
    )

    if document_notes:
        notes += " " + document_notes

    cur = con.execute(
        """
        INSERT INTO provenance_records (
            source_document_id,
            source_kind,
            source_name,
            source_reference,
            source_sha256,
            extraction_method,
            verification_status,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            "document",
            source_name,
            source_reference,
            sha256,
            EXTRACTION_METHOD,
            status,
            notes,
        ),
    )

    return cur.lastrowid, True


def bridge_observations(
    con: sqlite3.Connection,
) -> dict[str, int]:
    stats = {
        "legacy_occurrences": 0,
        "document_provenance_created": 0,
        "document_provenance_existing": 0,
        "observations_created": 0,
        "observations_existing": 0,
        "recovered_document_observations": 0,
        "missing_document_observations": 0,
    }

    documents = con.execute(
        """
        SELECT id
        FROM source_documents
        ORDER BY id
        """
    ).fetchall()

    provenance_by_document: dict[int, int] = {}

    for (document_id,) in documents:
        provenance_id, created = _document_provenance(
            con,
            document_id,
        )

        provenance_by_document[document_id] = (
            provenance_id
        )

        if created:
            stats[
                "document_provenance_created"
            ] += 1
        else:
            stats[
                "document_provenance_existing"
            ] += 1

    rows = con.execute(
        """
        SELECT
            occ.id,
            occ.phone_number_id,
            occ.source_document_id,
            occ.raw_value,
            occ.notes,
            cp.id AS contact_point_id,
            sd.verification_status
        FROM occurrences AS occ
        JOIN contact_points AS cp
          ON cp.legacy_phone_number_id =
             occ.phone_number_id
         AND cp.point_type='phone'
        JOIN source_documents AS sd
          ON sd.id = occ.source_document_id
        ORDER BY occ.id
        """
    ).fetchall()

    stats["legacy_occurrences"] = len(rows)

    for (
        occurrence_id,
        phone_number_id,
        document_id,
        raw_value,
        legacy_notes,
        contact_point_id,
        document_status,
    ) in rows:
        provenance_id = provenance_by_document[
            document_id
        ]

        # Deterministic idempotency key is encoded in
        # the notes because the v1 observation schema
        # intentionally has no legacy_occurrence_id.
        marker = (
            "legacy_occurrence_id="
            f"{occurrence_id}"
        )

        existing = con.execute(
            """
            SELECT id
            FROM contact_observations
            WHERE contact_point_id=?
              AND provenance_id=?
              AND observation_type=
                  'document_occurrence'
              AND notes LIKE ?
            ORDER BY id
            """,
            (
                contact_point_id,
                provenance_id,
                f"%{marker};%",
            ),
        ).fetchall()

        if len(existing) > 1:
            raise RuntimeError(
                "Duplicate observation already exists for "
                f"legacy occurrence {occurrence_id}"
            )

        if existing:
            stats["observations_existing"] += 1
            continue

        notes = (
            OBSERVATION_NOTE
            + " "
            + marker
            + f"; legacy_phone_number_id="
            + str(phone_number_id)
        )

        if legacy_notes:
            notes += (
                "; legacy_note="
                + legacy_notes
            )

        con.execute(
            """
            INSERT INTO contact_observations (
                contact_point_id,
                provenance_id,
                observation_type,
                observed_value,
                occurred_at,
                direction,
                classification,
                confidence,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contact_point_id,
                provenance_id,
                "document_occurrence",
                raw_value,
                None,
                None,
                "unknown",
                "unverified",
                notes,
            ),
        )

        stats["observations_created"] += 1

        if document_status == "recovered":
            stats[
                "recovered_document_observations"
            ] += 1

        elif document_status == "missing":
            stats[
                "missing_document_observations"
            ] += 1

    return stats
