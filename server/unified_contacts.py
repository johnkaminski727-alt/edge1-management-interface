"""Read-only Unified Contacts query model."""

from __future__ import annotations

import sqlite3
from contextlib import closing


class UnifiedContacts:
    def __init__(self, database: str):
        self.database = database

    def connect(self):
        con = sqlite3.connect(
            f"file:{self.database}?mode=ro",
            uri=True,
        )
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def summary(self):
        with closing(self.connect()) as con:
            def count(sql):
                return con.execute(sql).fetchone()[0]

            return {
                "entities": count(
                    "SELECT COUNT(*) FROM contact_entities"
                ),
                "organizations": count("""
                    SELECT COUNT(*)
                    FROM contact_entities
                    WHERE entity_type='organization'
                """),
                "people": count("""
                    SELECT COUNT(*)
                    FROM contact_entities
                    WHERE entity_type='person'
                """),
                "contact_points": count(
                    "SELECT COUNT(*) FROM contact_points"
                ),
                "phones": count("""
                    SELECT COUNT(*)
                    FROM contact_points
                    WHERE point_type='phone'
                """),
                "emails": count("""
                    SELECT COUNT(*)
                    FROM contact_points
                    WHERE point_type='email'
                """),
                "domains": count("""
                    SELECT COUNT(*)
                    FROM contact_points
                    WHERE point_type='domain'
                """),
                "assertions": count(
                    "SELECT COUNT(*) FROM contact_assertions"
                ),
                "confirmed": count("""
                    SELECT COUNT(*)
                    FROM contact_assertions
                    WHERE confidence='confirmed'
                """),
                "probable": count("""
                    SELECT COUNT(*)
                    FROM contact_assertions
                    WHERE confidence='probable'
                """),
                "provenance": count(
                    "SELECT COUNT(*) FROM provenance_records"
                ),
                "observations": count(
                    "SELECT COUNT(*) FROM contact_observations"
                ),
                "unassigned": count("""
                    SELECT COUNT(*)
                    FROM contact_points cp
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM contact_assertions ca
                        WHERE ca.contact_point_id=cp.id
                    )
                """),
                "unassigned_phones": count("""
                    SELECT COUNT(*)
                    FROM contact_points cp
                    WHERE cp.point_type='phone'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM contact_assertions ca
                          WHERE ca.contact_point_id=cp.id
                      )
                """),
                "candidate_correlations": count(
                    "SELECT COUNT(*) FROM candidate_correlations"
                ),
            }

    def entities(
        self,
        query="",
        entity_type="",
        limit=100,
        offset=0,
    ):
        """Return one row per canonical entity.

        Aliases participate in matching but remain separate
        evidence rather than replacing the canonical name.
        """
        limit = max(1, min(int(limit), 250))
        offset = max(0, int(offset))
        q = query.strip()
        like = f"%{q}%"

        clauses = []
        params = []

        if q:
            clauses.append("""
                (
                    e.canonical_name LIKE ?
                    OR e.display_name LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM contact_entity_aliases a
                        WHERE a.entity_id=e.id
                          AND a.alias_name LIKE ?
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM contact_assertions ca2
                        JOIN contact_points cp2
                          ON cp2.id=ca2.contact_point_id
                        WHERE ca2.entity_id=e.id
                          AND (
                              cp2.normalized_value LIKE ?
                              OR cp2.display_value LIKE ?
                          )
                    )
                )
            """)
            params.extend(
                [like, like, like, like, like]
            )

        if entity_type:
            clauses.append("e.entity_type=?")
            params.append(entity_type)

        where = (
            "WHERE " + " AND ".join(clauses)
            if clauses else ""
        )

        sql = f"""
            SELECT
                e.id AS entity_id,
                e.entity_type,
                e.canonical_name,
                e.display_name,
                e.lifecycle_status,
                e.verification_status,
                (
                    SELECT COUNT(*)
                    FROM contact_assertions ca
                    WHERE ca.entity_id=e.id
                ) AS contact_point_count,
                (
                    SELECT COUNT(*)
                    FROM contact_entity_aliases a
                    WHERE a.entity_id=e.id
                ) AS alias_count,
                (
                    SELECT COUNT(*)
                    FROM contact_attestations at
                    WHERE at.entity_id=e.id
                ) AS attestation_count
            FROM contact_entities e
            {where}
            ORDER BY
                e.canonical_name COLLATE NOCASE,
                e.id
            LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])

        with closing(self.connect()) as con:
            return [
                dict(row)
                for row in con.execute(sql, params)
            ]

    def search(self, query="", kind="all", limit=100):
        limit = max(1, min(int(limit), 250))
        q = query.strip()
        like = f"%{q}%"

        clauses = [
            "e.lifecycle_status='active'"
        ]
        params = []

        if q:
            clauses.append("""
                (
                    e.canonical_name LIKE ?
                    OR e.display_name LIKE ?
                    OR cp.normalized_value LIKE ?
                    OR cp.display_value LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM contact_entity_aliases a
                        WHERE a.entity_id=e.id
                          AND a.alias_name LIKE ?
                    )
                )
            """)
            params.extend(
                [like, like, like, like, like]
            )

        if kind == "organizations":
            clauses.append("e.entity_type='organization'")
        elif kind == "people":
            clauses.append("e.entity_type='person'")
        elif kind == "phones":
            clauses.append("cp.point_type='phone'")
        elif kind == "emails":
            clauses.append("cp.point_type='email'")
        elif kind == "domains":
            clauses.append("cp.point_type='domain'")

        where = (
            "WHERE " + " AND ".join(clauses)
            if clauses else ""
        )

        sql = f"""
            SELECT
                e.id AS entity_id,
                e.entity_type,
                e.canonical_name,
                e.display_name,
                e.lifecycle_status AS entity_lifecycle_status,
                e.verification_status,
                ca.id AS assertion_id,
                ca.valid_from AS assertion_valid_from,
                ca.valid_to AS assertion_valid_to,
                ca.confidence,
                ca.assertion_type,
                cp.id AS contact_point_id,
                cp.point_type,
                cp.normalized_value,
                cp.display_value,
                cp.lifecycle_status,
                cp.lifecycle_status AS contact_point_lifecycle_status
            FROM contact_entities AS e
            LEFT JOIN contact_assertions AS ca
              ON ca.entity_id=e.id
            LEFT JOIN contact_points AS cp
              ON cp.id=ca.contact_point_id
            {where}
            ORDER BY
                e.canonical_name COLLATE NOCASE,
                cp.point_type,
                cp.normalized_value
            LIMIT ?
        """

        params.append(limit)

        with closing(self.connect()) as con:
            return [
                dict(row)
                for row in con.execute(sql, params)
            ]

    def unassigned_phones(self, query="", limit=100):
        limit = max(1, min(int(limit), 250))
        q = query.strip()
        like = f"%{q}%"

        sql = """
            SELECT
                cp.id AS contact_point_id,
                cp.normalized_value,
                cp.display_value,
                cp.lifecycle_status,
                pn.status AS legacy_status,
                pn.occurrence_count
            FROM contact_points AS cp
            LEFT JOIN contact_assertions AS ca
              ON ca.contact_point_id=cp.id
            LEFT JOIN phone_numbers AS pn
              ON pn.id=cp.legacy_phone_number_id
            WHERE cp.point_type='phone'
              AND ca.id IS NULL
              AND (
                    ?=''
                    OR cp.normalized_value LIKE ?
                    OR cp.display_value LIKE ?
              )
            ORDER BY
                pn.occurrence_count DESC,
                cp.normalized_value
            LIMIT ?
        """

        with closing(self.connect()) as con:
            return [
                dict(row)
                for row in con.execute(
                    sql,
                    (q, like, like, limit),
                )
            ]

    def sources(
        self,
        query="",
        verification="",
        source_kind="",
        provenance_id=None,
        limit=100,
        offset=0,
    ):
        """Return provenance without treating it as identity."""
        limit = max(1, min(int(limit), 250))
        offset = max(0, int(offset))
        q = query.strip()
        like = f"%{q}%"

        clauses = []
        params = []

        if q:
            clauses.append("""
                (
                    pr.source_name LIKE ?
                    OR pr.source_reference LIKE ?
                    OR pr.source_url LIKE ?
                    OR pr.notes LIKE ?
                )
            """)
            params.extend(
                [like, like, like, like]
            )

        if verification:
            clauses.append(
                "pr.verification_status=?"
            )
            params.append(verification)

        if source_kind:
            clauses.append(
                "pr.source_kind=?"
            )
            params.append(source_kind)

        if provenance_id is not None:
            provenance_id = int(provenance_id)
            if provenance_id < 1:
                raise ValueError(
                    "provenance_id must be a positive integer"
                )
            clauses.append(
                "pr.id=?"
            )
            params.append(provenance_id)

        where = (
            "WHERE " + " AND ".join(clauses)
            if clauses else ""
        )

        sql = f"""
            SELECT
                pr.id AS provenance_id,
                pr.source_document_id,
                pr.source_kind,
                pr.source_name,
                pr.source_reference,
                pr.source_page,
                pr.source_url,
                pr.source_sha256,
                pr.extraction_method,
                pr.verification_status,
                pr.notes,
                (
                    SELECT COUNT(*)
                    FROM assertion_evidence ae
                    WHERE ae.provenance_id=pr.id
                ) AS assertion_links,
                (
                    SELECT COUNT(*)
                    FROM contact_observations co
                    WHERE co.provenance_id=pr.id
                ) AS observation_links
            FROM provenance_records pr
            {where}
            ORDER BY
                CASE pr.verification_status
                    WHEN 'missing_source' THEN 0
                    WHEN 'unverified' THEN 1
                    WHEN 'document_sourced' THEN 2
                    WHEN 'verified' THEN 3
                    ELSE 4
                END,
                pr.source_name COLLATE NOCASE,
                pr.id
            LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])

        with closing(self.connect()) as con:
            rows = [
                dict(row)
                for row in con.execute(sql, params)
            ]
            has_locations = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='provenance_source_locations'"
            ).fetchone() is not None
            if has_locations and rows:
                ids = [row["provenance_id"] for row in rows]
                placeholders = ",".join("?" for _ in ids)
                locations = {
                    row["provenance_id"]: dict(row)
                    for row in con.execute(
                        f"""SELECT provenance_id,location_kind,location AS resolved_location,
                                   source_sha256 AS resolved_sha256,match_method AS location_match_method,
                                   verification_status AS location_verification,last_verified_at
                            FROM provenance_source_locations
                            WHERE provenance_id IN ({placeholders})""",
                        ids,
                    )
                }
                for row in rows:
                    row.update(locations.get(row["provenance_id"], {}))
            return rows

    def observations(
        self,
        query="",
        classification="",
        verification="",
        contact_point_id=None,
        limit=100,
        offset=0,
    ):
        """Return observations without creating identity."""
        limit = max(1, min(int(limit), 250))
        offset = max(0, int(offset))
        q = query.strip()
        like = f"%{q}%"

        clauses = []
        params = []

        if q:
            clauses.append("""
                (
                    co.observed_value LIKE ?
                    OR cp.normalized_value LIKE ?
                    OR cp.display_value LIKE ?
                    OR pr.source_name LIKE ?
                    OR pr.source_reference LIKE ?
                )
            """)
            params.extend(
                [like, like, like, like, like]
            )

        if classification:
            clauses.append(
                "co.classification=?"
            )
            params.append(classification)

        if verification:
            clauses.append(
                "pr.verification_status=?"
            )
            params.append(verification)

        if contact_point_id is not None:
            clauses.append(
                "co.contact_point_id=?"
            )
            params.append(int(contact_point_id))

        where = (
            "WHERE " + " AND ".join(clauses)
            if clauses else ""
        )

        sql = f"""
            SELECT
                co.id AS observation_id,
                co.contact_point_id,
                co.provenance_id,
                co.observation_type,
                co.observed_value,
                co.occurred_at,
                co.direction,
                co.classification,
                co.confidence,
                co.notes,
                cp.point_type,
                cp.normalized_value,
                cp.display_value,
                pr.source_kind,
                pr.source_name,
                pr.source_reference,
                pr.source_page,
                pr.source_url,
                pr.verification_status
                    AS provenance_verification
            FROM contact_observations co
            LEFT JOIN contact_points cp
              ON cp.id=co.contact_point_id
            LEFT JOIN provenance_records pr
              ON pr.id=co.provenance_id
            {where}
            ORDER BY
                pr.source_name COLLATE NOCASE,
                cp.normalized_value,
                co.id
            LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])

        with closing(self.connect()) as con:
            return [
                dict(row)
                for row in con.execute(sql, params)
            ]


    def relationships(
        self,
        entity_id=None,
        contact_point_id=None,
        relationship_type="",
        confidence="",
        lifecycle_status="active",
        limit=100,
        offset=0,
    ):
        """
        Return durable Connections edges.

        Relationship identity, evidence and candidate review
        remain separate layers.
        """
        limit = max(1, min(int(limit), 250))
        offset = max(0, int(offset))

        clauses = []
        params = []

        if entity_id is not None:
            entity_id = int(entity_id)
            clauses.append(
                "(r.left_entity_id=? OR r.right_entity_id=?)"
            )
            params.extend([entity_id, entity_id])

        if contact_point_id is not None:
            contact_point_id = int(contact_point_id)
            clauses.append(
                "("
                "r.left_contact_point_id=? "
                "OR r.right_contact_point_id=?"
                ")"
            )
            params.extend(
                [contact_point_id, contact_point_id]
            )

        if relationship_type:
            clauses.append("r.relationship_type=?")
            params.append(relationship_type)

        if confidence:
            clauses.append("r.confidence=?")
            params.append(confidence)

        if lifecycle_status:
            clauses.append("r.lifecycle_status=?")
            params.append(lifecycle_status)

        where = (
            "WHERE " + " AND ".join(clauses)
            if clauses else ""
        )

        sql = f"""
            SELECT
                r.id AS relationship_id,
                r.left_entity_id,
                le.entity_type AS left_entity_type,
                le.canonical_name AS left_canonical_name,
                le.display_name AS left_display_name,
                r.left_contact_point_id,
                lcp.point_type AS left_point_type,
                lcp.normalized_value
                    AS left_normalized_value,
                lcp.display_value AS left_display_value,
                r.right_entity_id,
                re.entity_type AS right_entity_type,
                re.canonical_name AS right_canonical_name,
                re.display_name AS right_display_name,
                r.right_contact_point_id,
                rcp.point_type AS right_point_type,
                rcp.normalized_value
                    AS right_normalized_value,
                rcp.display_value AS right_display_value,
                r.relationship_type,
                r.confidence,
                r.lifecycle_status,
                r.directionality,
                r.notes,
                r.created_at,
                r.updated_at,
                (
                    SELECT COUNT(*)
                    FROM relationship_evidence rev
                    WHERE rev.relationship_id=r.id
                ) AS evidence_count
            FROM contact_relationships r
            LEFT JOIN contact_entities le
              ON le.id=r.left_entity_id
            LEFT JOIN contact_points lcp
              ON lcp.id=r.left_contact_point_id
            LEFT JOIN contact_entities re
              ON re.id=r.right_entity_id
            LEFT JOIN contact_points rcp
              ON rcp.id=r.right_contact_point_id
            {where}
            ORDER BY
                r.created_at DESC,
                r.id DESC
            LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])

        with closing(self.connect()) as con:
            return [
                dict(row)
                for row in con.execute(sql, params)
            ]

    def relationship_evidence(
        self,
        relationship_id,
        limit=100,
        offset=0,
    ):
        """
        Return provenance attached to one durable
        relationship.
        """
        relationship_id = int(relationship_id)
        limit = max(1, min(int(limit), 250))
        offset = max(0, int(offset))

        with closing(self.connect()) as con:
            return [
                dict(row)
                for row in con.execute(
                    """
                    SELECT
                        rev.id AS relationship_evidence_id,
                        rev.relationship_id,
                        rev.provenance_id,
                        rev.evidence_role,
                        rev.evidence_summary,
                        rev.created_at,
                        p.source_document_id,
                        p.source_kind,
                        p.source_name,
                        p.source_reference,
                        p.source_page,
                        p.source_url,
                        p.source_sha256,
                        p.extraction_method,
                        p.verification_status,
                        p.notes AS provenance_notes
                    FROM relationship_evidence rev
                    JOIN provenance_records p
                      ON p.id=rev.provenance_id
                    WHERE rev.relationship_id=?
                    ORDER BY
                        rev.created_at,
                        rev.id
                    LIMIT ? OFFSET ?
                    """,
                    (
                        relationship_id,
                        limit,
                        offset,
                    ),
                )
            ]

    def correlations(
        self,
        review_status="pending",
        correlation_type="",
        confidence="",
        entity_id=None,
        contact_point_id=None,
        limit=100,
        offset=0,
    ):
        """
        Return review-queue correlations separately from
        durable Connections edges.
        """
        limit = max(1, min(int(limit), 250))
        offset = max(0, int(offset))

        clauses = []
        params = []

        if review_status:
            clauses.append("c.review_status=?")
            params.append(review_status)

        if correlation_type:
            clauses.append("c.correlation_type=?")
            params.append(correlation_type)

        if confidence:
            clauses.append("c.confidence=?")
            params.append(confidence)

        if entity_id is not None:
            entity_id = int(entity_id)
            clauses.append(
                "(c.left_entity_id=? OR c.right_entity_id=?)"
            )
            params.extend([entity_id, entity_id])

        if contact_point_id is not None:
            contact_point_id = int(contact_point_id)
            clauses.append(
                "("
                "c.left_contact_point_id=? "
                "OR c.right_contact_point_id=?"
                ")"
            )
            params.extend(
                [contact_point_id, contact_point_id]
            )

        where = (
            "WHERE " + " AND ".join(clauses)
            if clauses else ""
        )

        sql = f"""
            SELECT
                c.id AS correlation_id,
                c.left_entity_id,
                le.entity_type AS left_entity_type,
                le.canonical_name AS left_canonical_name,
                le.display_name AS left_display_name,
                c.left_contact_point_id,
                lcp.point_type AS left_point_type,
                lcp.normalized_value
                    AS left_normalized_value,
                lcp.display_value AS left_display_value,
                c.right_entity_id,
                re.entity_type AS right_entity_type,
                re.canonical_name AS right_canonical_name,
                re.display_name AS right_display_name,
                c.right_contact_point_id,
                rcp.point_type AS right_point_type,
                rcp.normalized_value
                    AS right_normalized_value,
                rcp.display_value AS right_display_value,
                c.correlation_type,
                c.confidence,
                c.review_status,
                c.rationale,
                c.created_at,
                c.reviewed_at
            FROM candidate_correlations c
            LEFT JOIN contact_entities le
              ON le.id=c.left_entity_id
            LEFT JOIN contact_points lcp
              ON lcp.id=c.left_contact_point_id
            LEFT JOIN contact_entities re
              ON re.id=c.right_entity_id
            LEFT JOIN contact_points rcp
              ON rcp.id=c.right_contact_point_id
            {where}
            ORDER BY
                c.created_at DESC,
                c.id DESC
            LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])

        with closing(self.connect()) as con:
            return [
                dict(row)
                for row in con.execute(sql, params)
            ]


    def evidence(
        self,
        assertion_id=None,
        contact_point_id=None,
        entity_id=None,
        limit=100,
    ):
        """
        Return canonical assertions, assertion evidence,
        aliases, attestations and contextual observations
        as explicitly separate collections.
        """
        limit = max(1, min(int(limit), 250))

        supplied = sum(
            value is not None
            for value in (
                assertion_id,
                contact_point_id,
                entity_id,
            )
        )

        if supplied != 1:
            raise ValueError(
                "exactly one of assertion_id, "
                "contact_point_id or entity_id is required"
            )

        with closing(self.connect()) as con:
            point_ids = []
            entity_ids = []

            if assertion_id is not None:
                assertions = [
                    dict(row)
                    for row in con.execute(
                        """
                        SELECT
                            ca.id AS assertion_id,
                            ca.entity_id,
                            ca.contact_point_id,
                            ca.assertion_type,
                            ca.confidence,
                            ca.notes AS assertion_notes,
                            e.entity_type,
                            e.canonical_name,
                            e.display_name,
                            e.verification_status
                                AS entity_verification,
                            cp.point_type,
                            cp.normalized_value,
                            cp.display_value
                        FROM contact_assertions ca
                        JOIN contact_entities e
                          ON e.id=ca.entity_id
                        JOIN contact_points cp
                          ON cp.id=ca.contact_point_id
                        WHERE ca.id=?
                        LIMIT 1
                        """,
                        (int(assertion_id),),
                    )
                ]

                if assertions:
                    point_ids = [
                        assertions[0]["contact_point_id"]
                    ]
                    entity_ids = [
                        assertions[0]["entity_id"]
                    ]

            elif contact_point_id is not None:
                point_id = int(contact_point_id)
                point_ids = [point_id]

                assertions = [
                    dict(row)
                    for row in con.execute(
                        """
                        SELECT
                            ca.id AS assertion_id,
                            ca.entity_id,
                            ca.contact_point_id,
                            ca.assertion_type,
                            ca.confidence,
                            ca.notes AS assertion_notes,
                            e.entity_type,
                            e.canonical_name,
                            e.display_name,
                            e.verification_status
                                AS entity_verification,
                            cp.point_type,
                            cp.normalized_value,
                            cp.display_value
                        FROM contact_assertions ca
                        JOIN contact_entities e
                          ON e.id=ca.entity_id
                        JOIN contact_points cp
                          ON cp.id=ca.contact_point_id
                        WHERE ca.contact_point_id=?
                        ORDER BY ca.id
                        LIMIT ?
                        """,
                        (point_id, limit),
                    )
                ]

                entity_ids = sorted({
                    row["entity_id"]
                    for row in assertions
                })

            else:
                selected_entity_id = int(entity_id)
                entity_ids = [selected_entity_id]

                assertions = [
                    dict(row)
                    for row in con.execute(
                        """
                        SELECT
                            ca.id AS assertion_id,
                            ca.entity_id,
                            ca.contact_point_id,
                            ca.assertion_type,
                            ca.confidence,
                            ca.notes AS assertion_notes,
                            e.entity_type,
                            e.canonical_name,
                            e.display_name,
                            e.verification_status
                                AS entity_verification,
                            cp.point_type,
                            cp.normalized_value,
                            cp.display_value
                        FROM contact_assertions ca
                        JOIN contact_entities e
                          ON e.id=ca.entity_id
                        JOIN contact_points cp
                          ON cp.id=ca.contact_point_id
                        WHERE ca.entity_id=?
                        ORDER BY
                            cp.point_type,
                            cp.normalized_value,
                            ca.id
                        LIMIT ?
                        """,
                        (selected_entity_id, limit),
                    )
                ]

                point_ids = sorted({
                    row["contact_point_id"]
                    for row in assertions
                })

            assertion_ids = [
                row["assertion_id"]
                for row in assertions
            ]

            evidence_rows = []

            if assertion_ids:
                placeholders = ",".join(
                    "?" for _ in assertion_ids
                )

                evidence_rows = [
                    dict(row)
                    for row in con.execute(
                        f"""
                        SELECT
                            ae.id AS evidence_link_id,
                            ae.assertion_id,
                            ae.provenance_id,
                            ae.evidence_role,
                            ae.evidence_summary,
                            pr.source_kind,
                            pr.source_name,
                            pr.source_reference,
                            pr.source_page,
                            pr.source_url,
                            pr.verification_status,
                            pr.extraction_method,
                            pr.notes AS provenance_notes
                        FROM assertion_evidence ae
                        JOIN provenance_records pr
                          ON pr.id=ae.provenance_id
                        WHERE ae.assertion_id IN (
                            {placeholders}
                        )
                        ORDER BY
                            ae.assertion_id,
                            pr.id
                        LIMIT ?
                        """,
                        (*assertion_ids, limit),
                    )
                ]

            alias_rows = []

            if entity_ids:
                placeholders = ",".join(
                    "?" for _ in entity_ids
                )

                alias_rows = [
                    dict(row)
                    for row in con.execute(
                        f"""
                        SELECT
                            a.id AS alias_id,
                            a.entity_id,
                            a.alias_name,
                            a.alias_type,
                            a.confidence,
                            a.provenance_id,
                            a.source_path,
                            a.notes,
                            pr.source_kind,
                            pr.source_name,
                            pr.source_reference,
                            pr.source_page,
                            pr.source_url,
                            pr.verification_status
                                AS provenance_verification
                        FROM contact_entity_aliases a
                        LEFT JOIN provenance_records pr
                          ON pr.id=a.provenance_id
                        WHERE a.entity_id IN (
                            {placeholders}
                        )
                        ORDER BY
                            a.entity_id,
                            a.alias_name COLLATE NOCASE,
                            a.id
                        LIMIT ?
                        """,
                        (*entity_ids, limit),
                    )
                ]

            attestation_clauses = []
            attestation_params = []

            if entity_ids:
                placeholders = ",".join(
                    "?" for _ in entity_ids
                )
                attestation_clauses.append(
                    f"at.entity_id IN ({placeholders})"
                )
                attestation_params.extend(entity_ids)

            if point_ids:
                placeholders = ",".join(
                    "?" for _ in point_ids
                )
                attestation_clauses.append(
                    "at.contact_point_id IN "
                    f"({placeholders})"
                )
                attestation_params.extend(point_ids)

            attestation_rows = []

            if attestation_clauses:
                attestation_rows = [
                    dict(row)
                    for row in con.execute(
                        f"""
                        SELECT
                            at.id AS attestation_id,
                            at.entity_id,
                            at.contact_point_id,
                            at.provenance_id,
                            at.attribute,
                            at.attested_value,
                            at.classification,
                            at.verification_status,
                            at.source_path,
                            at.notes,
                            pr.source_kind,
                            pr.source_name,
                            pr.source_reference,
                            pr.source_page,
                            pr.source_url
                        FROM contact_attestations at
                        JOIN provenance_records pr
                          ON pr.id=at.provenance_id
                        WHERE (
                            {" OR ".join(attestation_clauses)}
                        )
                        ORDER BY
                            at.entity_id,
                            at.contact_point_id,
                            at.attribute,
                            at.id
                        LIMIT ?
                        """,
                        (*attestation_params, limit),
                    )
                ]

            observation_rows = []

            if point_ids:
                placeholders = ",".join(
                    "?" for _ in point_ids
                )

                observation_rows = [
                    dict(row)
                    for row in con.execute(
                        f"""
                        SELECT
                            co.id AS observation_id,
                            co.contact_point_id,
                            co.provenance_id,
                            co.observation_type,
                            co.observed_value,
                            co.occurred_at,
                            co.direction,
                            co.classification,
                            co.confidence,
                            co.notes,
                            pr.source_kind,
                            pr.source_name,
                            pr.source_reference,
                            pr.source_page,
                            pr.source_url,
                            pr.verification_status
                                AS provenance_verification
                        FROM contact_observations co
                        LEFT JOIN provenance_records pr
                          ON pr.id=co.provenance_id
                        WHERE co.contact_point_id IN (
                            {placeholders}
                        )
                        ORDER BY
                            pr.source_name COLLATE NOCASE,
                            co.contact_point_id,
                            co.id
                        LIMIT ?
                        """,
                        (*point_ids, limit),
                    )
                ]

            openpgp_rows = []
            openpgp_policies = []
            if point_ids:
                placeholders = ",".join("?" for _ in point_ids)
                openpgp_tables = {
                    row[0]
                    for row in con.execute(
                        """
                        SELECT name
                        FROM sqlite_master
                        WHERE type='table'
                          AND name IN (
                            'contact_openpgp_keys',
                            'contact_openpgp_policy'
                          )
                        """
                    )
                }
                if "contact_openpgp_keys" in openpgp_tables:
                    openpgp_rows = [
                        dict(row)
                        for row in con.execute(
                            f"""
                            SELECT k.id AS openpgp_key_id,k.contact_point_id,
                                   k.fingerprint,k.verification_status,k.source,
                                   k.expires_at,k.revoked_at,k.created_at,k.updated_at,
                                   cp.normalized_value AS email_address
                            FROM contact_openpgp_keys k
                            JOIN contact_points cp ON cp.id=k.contact_point_id
                            WHERE k.contact_point_id IN ({placeholders})
                            ORDER BY k.contact_point_id,k.created_at DESC,k.id DESC
                            """,
                            point_ids,
                        )
                    ]
                if "contact_openpgp_policy" in openpgp_tables:
                    openpgp_policies = [
                        dict(row)
                        for row in con.execute(
                            f"""
                            SELECT p.contact_point_id,p.mode,p.updated_at,
                                   cp.normalized_value AS email_address
                            FROM contact_openpgp_policy p
                            JOIN contact_points cp ON cp.id=p.contact_point_id
                            WHERE p.contact_point_id IN ({placeholders})
                            ORDER BY p.contact_point_id
                            """,
                            point_ids,
                        )
                    ]

            return {
                "assertions": assertions,
                "assertion_evidence": evidence_rows,
                "aliases": alias_rows,
                "attestations": attestation_rows,
                "observations": observation_rows,
                "openpgp_keys": openpgp_rows,
                "openpgp_policies": openpgp_policies,
            }
