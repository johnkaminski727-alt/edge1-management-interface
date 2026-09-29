#!/usr/bin/env python3
"""Bridge legacy Phone Intelligence records into Unified Contacts.

This module deliberately distinguishes:
- existence of an organization
- existence of a phone number
- an asserted relationship between them

Unresolved legacy associations never create contact assertions.
"""

from __future__ import annotations

import sqlite3


def bridge_organizations(conn: sqlite3.Connection) -> int:
    rows = conn.execute("""
        SELECT id, name
        FROM organizations
        ORDER BY id
    """).fetchall()

    inserted = 0

    for legacy_id, name in rows:
        cur = conn.execute("""
            INSERT OR IGNORE INTO contact_entities(
                entity_type,
                canonical_name,
                display_name,
                verification_status,
                legacy_organization_id,
                notes
            )
            VALUES (
                'organization',
                ?,
                ?,
                'verified',
                ?,
                'Bridged from released Phone Intelligence organization.'
            )
        """, (name, name, legacy_id))

        inserted += cur.rowcount

    return inserted


def bridge_phone_numbers(conn: sqlite3.Connection) -> int:
    rows = conn.execute("""
        SELECT
            id,
            normalized_number,
            display_number,
            status
        FROM phone_numbers
        ORDER BY id
    """).fetchall()

    inserted = 0

    for legacy_id, normalized, display, status in rows:
        lifecycle = (
            "retired"
            if status == "retired"
            else "unknown"
            if status == "unresolved"
            else "active"
        )

        cur = conn.execute("""
            INSERT OR IGNORE INTO contact_points(
                point_type,
                normalized_value,
                display_value,
                classification,
                lifecycle_status,
                legacy_phone_number_id
            )
            VALUES ('phone', ?, ?, ?, ?, ?)
        """, (
            normalized,
            display,
            "legacy_phone_intelligence",
            lifecycle,
            legacy_id,
        ))

        inserted += cur.rowcount

    return inserted


def bridge_associations(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("""
        SELECT
            a.id,
            a.phone_number_id,
            a.organization_id,
            a.confidence,
            a.association_label,
            a.research_notes
        FROM associations AS a
        ORDER BY a.id
    """).fetchall()

    stats = {
        "confirmed_assertions": 0,
        "probable_assertions": 0,
        "unresolved_skipped": 0,
        "disputed_skipped": 0,
        "missing_org_skipped": 0,
    }

    for (
        association_id,
        phone_id,
        org_id,
        confidence,
        label,
        notes,
    ) in rows:

        if confidence == "unresolved":
            stats["unresolved_skipped"] += 1
            continue

        if confidence == "disputed":
            stats["disputed_skipped"] += 1
            continue

        if org_id is None:
            stats["missing_org_skipped"] += 1
            continue

        entity = conn.execute("""
            SELECT id
            FROM contact_entities
            WHERE legacy_organization_id = ?
        """, (org_id,)).fetchone()

        point = conn.execute("""
            SELECT id
            FROM contact_points
            WHERE legacy_phone_number_id = ?
        """, (phone_id,)).fetchone()

        if entity is None or point is None:
            raise RuntimeError(
                f"bridge target missing for association {association_id}"
            )

        assertion_confidence = (
            "confirmed"
            if confidence == "confirmed"
            else "probable"
        )

        cur = conn.execute("""
            INSERT OR IGNORE INTO contact_assertions(
                entity_id,
                contact_point_id,
                assertion_type,
                confidence,
                notes
            )
            VALUES (?, ?, 'contact', ?, ?)
        """, (
            entity[0],
            point[0],
            assertion_confidence,
            (
                "Legacy Phone Intelligence association "
                f"{association_id}; label={label!r}; "
                f"research_notes={notes!r}"
            ),
        ))

        if cur.rowcount:
            stats[
                f"{assertion_confidence}_assertions"
            ] += 1

    return stats


def bridge_legacy(conn: sqlite3.Connection) -> dict[str, int]:
    conn.execute("PRAGMA foreign_keys=ON")

    stats = {
        "organizations_created": bridge_organizations(conn),
        "phone_points_created": bridge_phone_numbers(conn),
    }

    stats.update(bridge_associations(conn))
    return stats
