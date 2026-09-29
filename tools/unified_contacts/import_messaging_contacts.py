#!/usr/bin/env python3

"""Deterministic Messaging -> Unified Contacts importer."""

import argparse
import json
import sqlite3
from pathlib import Path

from tools.unified_contacts.schema_contacts_expansion import (
    apply_schema,
)


EXTRACTION_METHOD = "messaging_identity_registry_adapter_v1"

IDENTITY_SOURCE_NAME = "Edge1 Messaging Identity Registry"
INVENTORY_SOURCE_NAME = "Edge1 Mail Provider Inventory"


def provenance_family(source_path):
    """Resolve a candidate source path to its source registry."""

    inventory_markers = (
        "verified_round_trip_addresses",
        "configured_but_unverified_addresses",
        "observed_but_unregistered_addresses",
        "provider_admin_inventory",
    )

    if any(
        marker in source_path
        for marker in inventory_markers
    ):
        return "inventory"

    return "identity"


def existing_or_create_provenance(db, row):
    matches = db.execute(
        """
        SELECT id
        FROM provenance_records
        WHERE source_kind = ?
          AND source_name = ?
          AND COALESCE(source_reference, '') = ?
          AND COALESCE(extraction_method, '') = ?
        ORDER BY id
        """,
        (
            row["source_kind"],
            row["source_name"],
            row.get("source_reference") or "",
            row.get("extraction_method") or "",
        ),
    ).fetchall()

    if len(matches) > 1:
        raise RuntimeError(
            "Duplicate provenance identity for "
            + row["source_name"]
        )

    if matches:
        return matches[0][0], False

    cursor = db.execute(
        """
        INSERT INTO provenance_records (
            source_kind,
            source_name,
            source_reference,
            extraction_method,
            verification_status
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            row["source_kind"],
            row["source_name"],
            row.get("source_reference"),
            row.get("extraction_method"),
            row["verification_status"],
        ),
    )

    return cursor.lastrowid, True


def existing_or_create_entity(db, row):
    matches = db.execute(
        """
        SELECT id, entity_type
        FROM contact_entities
        WHERE lower(canonical_name) = lower(?)
        ORDER BY id
        """,
        (row["canonical_name"],),
    ).fetchall()

    if len(matches) > 1:
        raise RuntimeError(
            "Ambiguous existing canonical entity: "
            + row["canonical_name"]
        )

    if matches:
        entity_id, entity_type = matches[0]

        if entity_type != row["entity_type"]:
            raise RuntimeError(
                "Entity type conflict for "
                + row["canonical_name"]
            )

        return entity_id, False

    cursor = db.execute(
        """
        INSERT INTO contact_entities (
            entity_type,
            canonical_name,
            display_name,
            verification_status
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            row["entity_type"],
            row["canonical_name"],
            row["display_name"],
            row["verification_hint"],
        ),
    )

    return cursor.lastrowid, True


def existing_or_create_point(db, row):
    matches = db.execute(
        """
        SELECT id
        FROM contact_points
        WHERE point_type = ?
          AND normalized_value = ?
        ORDER BY id
        """,
        (
            row["point_type"],
            row["normalized_value"],
        ),
    ).fetchall()

    if len(matches) > 1:
        raise RuntimeError(
            "Duplicate contact point identity: "
            + row["source_key"]
        )

    if matches:
        return matches[0][0], False

    cursor = db.execute(
        """
        INSERT INTO contact_points (
            point_type,
            normalized_value,
            display_value,
            classification
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            row["point_type"],
            row["normalized_value"],
            row["display_value"],
            row["classification"],
        ),
    )

    return cursor.lastrowid, True


def existing_or_create_assertion(
    db,
    entity_id,
    point_id,
    confidence,
    source_path,
):
    matches = db.execute(
        """
        SELECT id, confidence
        FROM contact_assertions
        WHERE entity_id = ?
          AND contact_point_id = ?
          AND assertion_type = 'contact'
        ORDER BY id
        """,
        (
            entity_id,
            point_id,
        ),
    ).fetchall()

    if len(matches) > 1:
        raise RuntimeError(
            "Duplicate contact assertion"
        )

    if matches:
        return matches[0][0], False

    cursor = db.execute(
        """
        INSERT INTO contact_assertions (
            entity_id,
            contact_point_id,
            assertion_type,
            confidence,
            notes
        )
        VALUES (?, ?, 'contact', ?, ?)
        """,
        (
            entity_id,
            point_id,
            confidence,
            (
                "Messaging identity registry relationship; "
                f"source_path={source_path}"
            ),
        ),
    )

    return cursor.lastrowid, True


def existing_or_create_evidence(
    db,
    assertion_id,
    provenance_id,
    source_path,
):
    matches = db.execute(
        """
        SELECT id
        FROM assertion_evidence
        WHERE assertion_id = ?
          AND provenance_id = ?
          AND evidence_role = 'supports'
        ORDER BY id
        """,
        (
            assertion_id,
            provenance_id,
        ),
    ).fetchall()

    if len(matches) > 1:
        raise RuntimeError(
            "Duplicate assertion evidence"
        )

    if matches:
        return matches[0][0], False

    cursor = db.execute(
        """
        INSERT INTO assertion_evidence (
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
            (
                "Explicit messaging identity relationship; "
                f"source_path={source_path}"
            ),
        ),
    )

    return cursor.lastrowid, True


def existing_or_create_alias(
    db,
    entity_id,
    provenance_id,
    row,
):
    matches = db.execute(
        """
        SELECT id
        FROM contact_entity_aliases
        WHERE entity_id = ?
          AND alias_name = ?
          AND alias_type = ?
          AND provenance_id = ?
          AND source_path = ?
        ORDER BY id
        """,
        (
            entity_id,
            row["alias_name"],
            row["alias_type"],
            provenance_id,
            row["source_path"],
        ),
    ).fetchall()

    if len(matches) > 1:
        raise RuntimeError(
            "Duplicate entity alias"
        )

    if matches:
        return matches[0][0], False

    cursor = db.execute(
        """
        INSERT INTO contact_entity_aliases (
            entity_id,
            alias_name,
            alias_type,
            confidence,
            provenance_id,
            source_path
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            entity_id,
            row["alias_name"],
            row["alias_type"],
            row["confidence"],
            provenance_id,
            row["source_path"],
        ),
    )

    return cursor.lastrowid, True


def existing_or_create_attestation(
    db,
    entity_id,
    point_id,
    provenance_id,
    row,
):
    matches = db.execute(
        """
        SELECT id
        FROM contact_attestations
        WHERE entity_id IS ?
          AND contact_point_id IS ?
          AND provenance_id = ?
          AND attribute = ?
          AND attested_value = ?
          AND COALESCE(classification, '') = ?
          AND source_path = ?
        ORDER BY id
        """,
        (
            entity_id,
            point_id,
            provenance_id,
            row["attribute"],
            row["value"],
            row.get("classification") or "",
            row["source_path"],
        ),
    ).fetchall()

    if len(matches) > 1:
        raise RuntimeError(
            "Duplicate contact attestation"
        )

    if matches:
        return matches[0][0], False

    cursor = db.execute(
        """
        INSERT INTO contact_attestations (
            entity_id,
            contact_point_id,
            provenance_id,
            attribute,
            attested_value,
            classification,
            verification_status,
            source_path
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity_id,
            point_id,
            provenance_id,
            row["attribute"],
            row["value"],
            row.get("classification"),
            row["verification_hint"],
            row["source_path"],
        ),
    )

    return cursor.lastrowid, True


def import_manifest(db, manifest):
    apply_schema(db)

    stats = {
        "provenance_created": 0,
        "provenance_existing": 0,
        "entities_created": 0,
        "entities_existing": 0,
        "points_created": 0,
        "points_existing": 0,
        "assertions_created": 0,
        "assertions_existing": 0,
        "evidence_created": 0,
        "evidence_existing": 0,
        "aliases_created": 0,
        "aliases_existing": 0,
        "attestations_created": 0,
        "attestations_existing": 0,
    }

    provenance = {}

    for row in manifest["provenance"]:
        provenance_id, created = (
            existing_or_create_provenance(
                db,
                row,
            )
        )

        if row["source_name"] == IDENTITY_SOURCE_NAME:
            provenance["identity"] = provenance_id
        elif row["source_name"] == INVENTORY_SOURCE_NAME:
            provenance["inventory"] = provenance_id
        else:
            raise RuntimeError(
                "Unexpected provenance source: "
                + row["source_name"]
            )

        stats[
            "provenance_created"
            if created
            else "provenance_existing"
        ] += 1

    if set(provenance) != {
        "identity",
        "inventory",
    }:
        raise RuntimeError(
            "Expected exactly identity and inventory provenance"
        )

    entities = {}

    for row in manifest["entities"]:
        entity_id, created = (
            existing_or_create_entity(
                db,
                row,
            )
        )

        entities[row["source_key"]] = entity_id

        stats[
            "entities_created"
            if created
            else "entities_existing"
        ] += 1

    points = {}

    for row in manifest["contact_points"]:
        point_id, created = (
            existing_or_create_point(
                db,
                row,
            )
        )

        points[row["source_key"]] = point_id

        stats[
            "points_created"
            if created
            else "points_existing"
        ] += 1

    for row in manifest["relationships"]:
        entity_id = entities[
            row["source_entity_key"]
        ]

        point_id = points[
            row["source_point_key"]
        ]

        assertion_id, created = (
            existing_or_create_assertion(
                db,
                entity_id,
                point_id,
                row["confidence"],
                row["source_path"],
            )
        )

        stats[
            "assertions_created"
            if created
            else "assertions_existing"
        ] += 1

        evidence_id, created = (
            existing_or_create_evidence(
                db,
                assertion_id,
                provenance["identity"],
                row["source_path"],
            )
        )

        stats[
            "evidence_created"
            if created
            else "evidence_existing"
        ] += 1

    for row in manifest["aliases"]:
        _, created = existing_or_create_alias(
            db,
            entities[row["legal_entity_key"]],
            provenance["identity"],
            row,
        )

        stats[
            "aliases_created"
            if created
            else "aliases_existing"
        ] += 1

    for row in manifest["attestations"]:
        entity_id = entities.get(
            row["subject_key"]
        )

        point_id = points.get(
            row["subject_key"]
        )

        if (
            (entity_id is None)
            ==
            (point_id is None)
        ):
            raise RuntimeError(
                "Attestation subject must resolve "
                "to exactly one entity or point: "
                + row["subject_key"]
            )

        family = provenance_family(
            row["source_path"]
        )

        _, created = (
            existing_or_create_attestation(
                db,
                entity_id,
                point_id,
                provenance[family],
                row,
            )
        )

        stats[
            "attestations_created"
            if created
            else "attestations_existing"
        ] += 1

    return stats


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--database",
        required=True,
    )

    parser.add_argument(
        "--manifest",
        required=True,
    )

    parser.add_argument(
        "--commit",
        action="store_true",
    )

    args = parser.parse_args()

    manifest = json.loads(
        Path(args.manifest).read_text()
    )

    db = sqlite3.connect(args.database)
    db.execute("PRAGMA foreign_keys = ON")

    db.execute("BEGIN")

    stats = import_manifest(
        db,
        manifest,
    )

    integrity = db.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

    fk = db.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    if integrity != "ok":
        raise RuntimeError(
            "integrity_check failed: "
            + str(integrity)
        )

    if fk:
        raise RuntimeError(
            "foreign_key_check failed: "
            + repr(fk)
        )

    print(
        json.dumps(
            stats,
            indent=2,
            sort_keys=True,
        )
    )

    if args.commit:
        db.commit()
        print("transaction: COMMITTED")
    else:
        db.rollback()
        print("transaction: ROLLED BACK")

    db.close()


if __name__ == "__main__":
    main()
