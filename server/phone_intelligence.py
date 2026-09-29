#!/usr/bin/env python3
"""Read-only Phone Intelligence data access for Edge1."""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


DEFAULT_DB = Path(
    "/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite"
)

VALID_STATUSES = {
    "confirmed",
    "probable",
    "unresolved",
    "disputed",
    "retired",
}

DIGITS = re.compile(r"\D+")


class PhoneIntelligenceError(ValueError):
    pass


class PhoneIntelligenceStore:
    def __init__(self, database=DEFAULT_DB):
        self.database = Path(database)

    def connect(self):
        # SQLite URI mode=ro enforces the read-only boundary
        # independently of application intent.
        uri = f"file:{self.database}?mode=ro"

        conn = sqlite3.connect(
            uri,
            uri=True,
            timeout=5,
        )

        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA query_only=ON")

        return conn

    @staticmethod
    def _bounded_int(value, default, minimum, maximum):
        if value in (None, ""):
            return default

        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise PhoneIntelligenceError(
                "invalid integer parameter"
            ) from exc

        if number < minimum or number > maximum:
            raise PhoneIntelligenceError(
                f"integer parameter must be between "
                f"{minimum} and {maximum}"
            )

        return number

    @staticmethod
    def _status(value):
        if value in (None, ""):
            return None

        status = str(value).strip().lower()

        if status not in VALID_STATUSES:
            raise PhoneIntelligenceError(
                "invalid phone status"
            )

        return status

    def dashboard(self):
        with closing(self.connect()) as conn:
            status_rows = conn.execute(
                """
                SELECT status, COUNT(*) AS total
                FROM phone_numbers
                GROUP BY status
                ORDER BY status
                """
            ).fetchall()

            statuses = {
                row["status"]: row["total"]
                for row in status_rows
            }

            return {
                "total_numbers": conn.execute(
                    "SELECT COUNT(*) FROM phone_numbers"
                ).fetchone()[0],
                "aggregate_occurrences": conn.execute(
                    """
                    SELECT COALESCE(SUM(occurrence_count), 0)
                    FROM phone_numbers
                    """
                ).fetchone()[0],
                "source_documents": conn.execute(
                    "SELECT COUNT(*) FROM source_documents"
                ).fetchone()[0],
                "organizations": conn.execute(
                    "SELECT COUNT(*) FROM organizations"
                ).fetchone()[0],
                "bill_relationships": conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM occurrences
                    WHERE occurrence_type='bill-reference'
                    """
                ).fetchone()[0],
                "statuses": statuses,
            }

    def list_phones(
        self,
        *,
        query=None,
        status=None,
        npa=None,
        limit=50,
        offset=0,
    ):
        status = self._status(status)

        limit = self._bounded_int(
            limit, 50, 1, 200
        )

        offset = self._bounded_int(
            offset, 0, 0, 1000000
        )

        clauses = []
        params = []

        if status:
            clauses.append("p.status = ?")
            params.append(status)

        if npa:
            npa = DIGITS.sub("", str(npa))

            if len(npa) != 3:
                raise PhoneIntelligenceError(
                    "NPA must contain exactly three digits"
                )

            clauses.append("p.npa = ?")
            params.append(npa)

        if query:
            query = str(query).strip()

            if len(query) > 120:
                raise PhoneIntelligenceError(
                    "query is too long"
                )

            if query:
                digits = DIGITS.sub("", query)

                search_clauses = [
                    "LOWER(COALESCE(a.association_label,'')) "
                    "LIKE LOWER(?)",
                    "LOWER(COALESCE(o.name,'')) LIKE LOWER(?)",
                    "LOWER(COALESCE(o.region,'')) LIKE LOWER(?)",
                    "LOWER(COALESCE(o.organization_type,'')) "
                    "LIKE LOWER(?)",
                ]

                like = f"%{query}%"

                params.extend(
                    [like, like, like, like]
                )

                if digits:
                    search_clauses.extend([
                        "REPLACE(REPLACE(REPLACE("
                        "REPLACE(p.display_number,'(',''),"
                        "')',''),'-',''),' ','') LIKE ?",
                        "p.normalized_number LIKE ?",
                    ])

                    params.extend([
                        f"%{digits}%",
                        f"%{digits}%",
                    ])

                clauses.append(
                    "(" + " OR ".join(search_clauses) + ")"
                )

        where = (
            " WHERE " + " AND ".join(clauses)
            if clauses
            else ""
        )

        base = """
            FROM phone_numbers AS p
            LEFT JOIN associations AS a
              ON a.phone_number_id = p.id
            LEFT JOIN organizations AS o
              ON o.id = a.organization_id
        """

        with closing(self.connect()) as conn:
            total = conn.execute(
                "SELECT COUNT(DISTINCT p.id) "
                + base
                + where,
                params,
            ).fetchone()[0]

            rows = conn.execute(
                """
                SELECT DISTINCT
                    p.id,
                    p.display_number,
                    p.normalized_number,
                    p.npa,
                    p.status,
                    p.occurrence_count,
                    a.association_label,
                    a.confidence,
                    o.organization_type AS category,
                    o.region AS location
                """
                + base
                + where
                + """
                ORDER BY
                    CASE p.status
                        WHEN 'confirmed' THEN 0
                        WHEN 'probable' THEN 1
                        WHEN 'unresolved' THEN 2
                        ELSE 3
                    END,
                    p.display_number
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "phones": [dict(row) for row in rows],
        }

    def phone_detail(self, phone_id):
        phone_id = self._bounded_int(
            phone_id, None, 1, 2147483647
        )

        with closing(self.connect()) as conn:
            phone = conn.execute(
                """
                SELECT
                    p.*,
                    a.id AS association_id,
                    a.association_label,
                    a.confidence,
                    a.research_notes,
                    o.id AS organization_id,
                    o.name AS organization_name,
                    o.organization_type AS category,
                    o.city,
                    o.region,
                    o.country,
                    o.website
                FROM phone_numbers AS p
                LEFT JOIN associations AS a
                  ON a.phone_number_id = p.id
                LEFT JOIN organizations AS o
                  ON o.id = a.organization_id
                WHERE p.id = ?
                """,
                (phone_id,),
            ).fetchone()

            if phone is None:
                return None

            evidence = conn.execute(
                """
                SELECT
                    id,
                    evidence_type,
                    source_title,
                    source_url,
                    source_reference,
                    evidence_summary,
                    verification_status,
                    retrieved_at,
                    created_at
                FROM evidence
                WHERE association_id = ?
                ORDER BY id
                """,
                (phone["association_id"],),
            ).fetchall()

            sources = conn.execute(
                """
                SELECT
                    d.id,
                    d.source_name,
                    d.source_reference,
                    d.statement_date,
                    d.verification_status,
                    d.notes,
                    COUNT(x.id) AS relationships
                FROM occurrences AS x
                JOIN source_documents AS d
                  ON d.id = x.source_document_id
                WHERE x.phone_number_id = ?
                GROUP BY d.id
                ORDER BY d.source_name
                """,
                (phone_id,),
            ).fetchall()

        result = dict(phone)
        result["evidence"] = [
            dict(row) for row in evidence
        ]
        result["sources"] = [
            dict(row) for row in sources
        ]

        return result

    def list_sources(self, *, limit=100, offset=0):
        limit = self._bounded_int(
            limit, 100, 1, 200
        )

        offset = self._bounded_int(
            offset, 0, 0, 1000000
        )

        with closing(self.connect()) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM source_documents"
            ).fetchone()[0]

            rows = conn.execute(
                """
                SELECT
                    d.id,
                    d.source_name,
                    d.source_reference,
                    d.statement_date,
                    d.verification_status,
                    d.notes,
                    COUNT(DISTINCT x.phone_number_id)
                        AS phone_numbers,
                    COUNT(x.id) AS relationships
                FROM source_documents AS d
                LEFT JOIN occurrences AS x
                  ON x.source_document_id = d.id
                GROUP BY d.id
                ORDER BY d.source_name
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "sources": [dict(row) for row in rows],
        }


def parse_phone_api_path(path):
    parsed = urlsplit(path)

    if parsed.path == "/v1/intelligence/phones":
        params = parse_qs(
            parsed.query,
            keep_blank_values=False,
        )

        def one(name):
            values = params.get(name)
            return values[-1] if values else None

        return (
            "phones",
            {
                "query": one("q"),
                "status": one("status"),
                "npa": one("npa"),
                "limit": one("limit"),
                "offset": one("offset"),
            },
        )

    if parsed.path == "/v1/intelligence/dashboard":
        return "dashboard", {}

    if parsed.path == "/v1/intelligence/sources":
        params = parse_qs(parsed.query)

        return (
            "sources",
            {
                "limit": (
                    params.get("limit", [None])[-1]
                ),
                "offset": (
                    params.get("offset", [None])[-1]
                ),
            },
        )

    prefix = "/v1/intelligence/phones/"

    if parsed.path.startswith(prefix):
        identifier = parsed.path[len(prefix):]

        if (
            not identifier
            or "/" in identifier
            or parsed.query
        ):
            return None

        return "phone", {"phone_id": identifier}

    return None
