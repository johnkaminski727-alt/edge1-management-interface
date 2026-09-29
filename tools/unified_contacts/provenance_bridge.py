#!/usr/bin/env python3
"""Deterministic legacy Phone Intelligence provenance bridge.

Rules:
- preserve every legacy evidence record as provenance;
- never infer source_document_id from textual similarity;
- only confirmed/probable associations support canonical assertions;
- unresolved/disputed associations remain provenance only;
- repeated execution must not duplicate bridged records;
- entity verification is derived conservatively from actual legacy
  association/evidence state.
"""

from __future__ import annotations

import sqlite3


BRIDGE_METHOD = "legacy_phone_intelligence_bridge"


def _source_kind(evidence_type: str | None) -> str:
    value = (evidence_type or "").strip().lower()

    mapping = {
        "public-research": "public_source",
        "public_source": "public_source",
        "public-source": "public_source",
        "manual": "manual",
        "manual-review": "manual",
        "register": "register",
        "registry": "register",
        "email": "email",
        "mail": "email",
        "document": "document",
        "bill": "document",
        "invoice": "document",
    }

    return mapping.get(value, "import")


def _verification_status(value: str | None) -> str:
    value = (value or "unverified").strip().lower()

    allowed = {
        "verified",
        "unverified",
        "superseded",
        "disputed",
    }

    return value if value in allowed else "unverified"


def _source_name(
    evidence_type: str | None,
    source_title: str | None,
) -> str:
    title = (source_title or "").strip()

    if title:
        return title

    kind = (evidence_type or "").strip()

    if kind:
        return f"Legacy Phone Intelligence {kind}"

    return "Legacy Phone Intelligence evidence"


def _bridge_marker(
    evidence_id: int,
    association_id: int,
) -> str:
    return (
        f"legacy_evidence_id={evidence_id}; "
        f"association_id={association_id};"
    )


def _legacy_assertion(
    conn: sqlite3.Connection,
    association_id: int,
):
    return conn.execute(
        """
        SELECT
            ca.id,
            a.confidence
        FROM associations AS a
        JOIN contact_entities AS ce
          ON ce.legacy_organization_id = a.organization_id
        JOIN contact_points AS cp
          ON cp.legacy_phone_number_id = a.phone_number_id
        JOIN contact_assertions AS ca
          ON ca.entity_id = ce.id
         AND ca.contact_point_id = cp.id
         AND ca.assertion_type = 'contact'
        WHERE a.id = ?
          AND a.organization_id IS NOT NULL
          AND a.confidence IN ('confirmed', 'probable')
        """,
        (association_id,),
    ).fetchone()


def _existing_provenance(
    conn: sqlite3.Connection,
    evidence_id: int,
    association_id: int,
):
    marker = _bridge_marker(
        evidence_id,
        association_id,
    )

    rows = conn.execute(
        """
        SELECT id
        FROM provenance_records
        WHERE extraction_method = ?
          AND notes LIKE ?
        ORDER BY id
        """,
        (
            BRIDGE_METHOD,
            f"%{marker}%",
        ),
    ).fetchall()

    if len(rows) > 1:
        raise RuntimeError(
            "Duplicate provenance already exists for "
            f"legacy evidence {evidence_id}"
        )

    return rows[0][0] if rows else None


def bridge_provenance(
    conn: sqlite3.Connection,
) -> dict[str, int]:
    conn.execute("PRAGMA foreign_keys=ON")

    stats = {
        "legacy_evidence": 0,
        "provenance_created": 0,
        "provenance_existing": 0,
        "assertion_links_created": 0,
        "assertion_links_existing": 0,
        "confirmed_links": 0,
        "probable_links": 0,
        "unresolved_preserved_only": 0,
        "disputed_preserved_only": 0,
    }

    rows = conn.execute(
        """
        SELECT
            e.id,
            e.association_id,
            e.evidence_type,
            e.source_title,
            e.source_url,
            e.source_reference,
            e.evidence_summary,
            e.verification_status,
            e.retrieved_at,
            e.created_at,
            a.confidence
        FROM evidence AS e
        JOIN associations AS a
          ON a.id = e.association_id
        ORDER BY e.id
        """
    ).fetchall()

    for (
        evidence_id,
        association_id,
        evidence_type,
        source_title,
        source_url,
        source_reference,
        evidence_summary,
        verification_status,
        retrieved_at,
        created_at,
        association_confidence,
    ) in rows:
        stats["legacy_evidence"] += 1

        provenance_id = _existing_provenance(
            conn,
            evidence_id,
            association_id,
        )

        if provenance_id is None:
            marker = _bridge_marker(
                evidence_id,
                association_id,
            )

            notes = (
                marker + " "
                f"evidence_type={evidence_type!r}; "
                f"retrieved_at={retrieved_at!r}. "
                "Bridged from legacy Phone Intelligence. "
                "No source_document_id inferred from textual "
                "source references."
            )

            cur = conn.execute(
                """
                INSERT INTO provenance_records(
                    source_document_id,
                    source_kind,
                    source_name,
                    source_reference,
                    source_page,
                    source_url,
                    source_sha256,
                    extraction_method,
                    verification_status,
                    notes,
                    created_at
                )
                VALUES (
                    NULL, ?, ?, ?, NULL, ?, NULL, ?, ?, ?,
                    COALESCE(?, CURRENT_TIMESTAMP)
                )
                """,
                (
                    _source_kind(evidence_type),
                    _source_name(
                        evidence_type,
                        source_title,
                    ),
                    source_reference,
                    source_url,
                    BRIDGE_METHOD,
                    _verification_status(
                        verification_status
                    ),
                    notes,
                    created_at,
                ),
            )

            provenance_id = cur.lastrowid
            stats["provenance_created"] += 1
        else:
            stats["provenance_existing"] += 1

        if association_confidence == "unresolved":
            stats[
                "unresolved_preserved_only"
            ] += 1
            continue

        if association_confidence == "disputed":
            stats[
                "disputed_preserved_only"
            ] += 1
            continue

        assertion = _legacy_assertion(
            conn,
            association_id,
        )

        if assertion is None:
            raise RuntimeError(
                "No deterministic Unified Contacts assertion "
                f"for legacy association {association_id}"
            )

        assertion_id, resolved_confidence = assertion

        existing_link = conn.execute(
            """
            SELECT id
            FROM assertion_evidence
            WHERE assertion_id = ?
              AND provenance_id = ?
              AND evidence_role = 'supports'
            """,
            (
                assertion_id,
                provenance_id,
            ),
        ).fetchone()

        if existing_link is None:
            conn.execute(
                """
                INSERT INTO assertion_evidence(
                    assertion_id,
                    provenance_id,
                    evidence_role,
                    evidence_summary
                )
                VALUES (?, ?, 'supports', ?)
                """,
                (
                    assertion_id,
                    provenance_id,
                    evidence_summary,
                ),
            )

            stats[
                "assertion_links_created"
            ] += 1
        else:
            stats[
                "assertion_links_existing"
            ] += 1

        stats[
            f"{resolved_confidence}_links"
        ] += 1

    return stats


def reconcile_entity_verification(
    conn: sqlite3.Connection,
) -> dict[str, int]:
    """Correct legacy bridged organization verification conservatively."""

    conn.execute("PRAGMA foreign_keys=ON")

    stats = {
        "entities_examined": 0,
        "verified": 0,
        "unverified": 0,
        "disputed": 0,
        "updated": 0,
    }

    entities = conn.execute(
        """
        SELECT
            id,
            legacy_organization_id,
            verification_status
        FROM contact_entities
        WHERE entity_type = 'organization'
          AND legacy_organization_id IS NOT NULL
        ORDER BY id
        """
    ).fetchall()

    for entity_id, legacy_org_id, current in entities:
        stats["entities_examined"] += 1

        evidence = conn.execute(
            """
            SELECT
                a.confidence,
                e.verification_status
            FROM associations AS a
            LEFT JOIN evidence AS e
              ON e.association_id = a.id
            WHERE a.organization_id = ?
            """,
            (legacy_org_id,),
        ).fetchall()

        if any(
            confidence == "confirmed"
            and evidence_status == "verified"
            for confidence, evidence_status in evidence
        ):
            target = "verified"

        elif any(
            confidence == "disputed"
            or evidence_status == "disputed"
            for confidence, evidence_status in evidence
        ):
            target = "disputed"

        else:
            # Probable/unverified evidence establishes neither
            # verified identity nor document sourcing.
            target = "unverified"

        stats[target] += 1

        if current != target:
            conn.execute(
                """
                UPDATE contact_entities
                SET verification_status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (target, entity_id),
            )

            stats["updated"] += 1

    return stats
