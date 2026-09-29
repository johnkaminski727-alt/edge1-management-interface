#!/usr/bin/env python3

import argparse
import json
import sqlite3
from pathlib import Path

from tools.unified_contacts.adapters.messaging import extract


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--identities",
        required=True,
    )

    parser.add_argument(
        "--inventory",
        required=True,
    )

    parser.add_argument(
        "--database",
        required=True,
    )

    parser.add_argument(
        "--output",
        required=True,
    )

    args = parser.parse_args()

    manifest = extract(
        args.identities,
        args.inventory,
    )

    payload = manifest.as_dict()

    db = sqlite3.connect(
        f"file:{Path(args.database)}?mode=ro",
        uri=True,
    )

    existing_entities = {
        row[0].casefold(): {
            "id": row[1],
            "canonical_name": row[0],
            "verification_status": row[2],
        }
        for row in db.execute(
            """
            SELECT
                canonical_name,
                id,
                verification_status
            FROM contact_entities
            """
        )
    }

    existing_points = {
        (row[0], row[1]): {
            "id": row[2],
            "display_value": row[3],
        }
        for row in db.execute(
            """
            SELECT
                point_type,
                normalized_value,
                id,
                display_value
            FROM contact_points
            """
        )
    }

    db.close()

    collisions = {
        "entity_exact_name": [],
        "contact_point_exact": [],
    }

    for candidate in manifest.entities:
        existing = existing_entities.get(
            candidate.canonical_name.casefold()
        )

        if existing:
            collisions[
                "entity_exact_name"
            ].append({
                "candidate": candidate.__dict__,
                "existing": existing,
            })

    for candidate in manifest.contact_points:
        existing = existing_points.get(
            (
                candidate.point_type,
                candidate.normalized_value,
            )
        )

        if existing:
            collisions[
                "contact_point_exact"
            ].append({
                "candidate": candidate.__dict__,
                "existing": existing,
            })

    payload["production_collisions"] = collisions

    payload["summary"] = {
        "entities": len(manifest.entities),
        "contact_points": len(
            manifest.contact_points
        ),
        "relationships": len(
            manifest.relationships
        ),
        "provenance": len(
            manifest.provenance
        ),
        "aliases": len(
            manifest.aliases
        ),
        "attestations": len(
            manifest.attestations
        ),
        "review_items": len(
            manifest.review_items
        ),
        "entity_exact_name_collisions": len(
            collisions["entity_exact_name"]
        ),
        "contact_point_exact_collisions": len(
            collisions["contact_point_exact"]
        ),
    }

    Path(args.output).write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print(
        json.dumps(
            payload["summary"],
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
