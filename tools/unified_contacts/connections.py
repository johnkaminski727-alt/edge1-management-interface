from dataclasses import dataclass
import sqlite3

from tools.unified_contacts.relationship_policy import (
    can_promote_candidate,
    promotion_confidence,
    relationship_definition,
    validate_relationship,
)


@dataclass(frozen=True)
class PromotionResult:
    candidate_id: int
    relationship_id: int
    relationship_created: bool
    evidence_created: bool


def _candidate(
    db: sqlite3.Connection,
    candidate_id: int,
):
    row = db.execute(
        """
        SELECT *
        FROM candidate_correlations
        WHERE id=?
        """,
        (candidate_id,),
    ).fetchone()

    if row is None:
        raise ValueError(
            f"candidate not found: {candidate_id}"
        )

    return row


def accept_candidate(
    db: sqlite3.Connection,
    candidate_id: int,
) -> None:
    row = _candidate(
        db,
        candidate_id,
    )

    status = row["review_status"]

    if status == "accepted":
        return

    if status != "pending":
        raise ValueError(
            "only pending candidates can be accepted"
        )

    db.execute(
        """
        UPDATE candidate_correlations
        SET
            review_status='accepted',
            reviewed_at=CURRENT_TIMESTAMP
        WHERE id=?
          AND review_status='pending'
        """,
        (candidate_id,),
    )


def reject_candidate(
    db: sqlite3.Connection,
    candidate_id: int,
) -> None:
    row = _candidate(
        db,
        candidate_id,
    )

    status = row["review_status"]

    if status == "rejected":
        return

    if status != "pending":
        raise ValueError(
            "only pending candidates can be rejected"
        )

    db.execute(
        """
        UPDATE candidate_correlations
        SET
            review_status='rejected',
            reviewed_at=CURRENT_TIMESTAMP
        WHERE id=?
          AND review_status='pending'
        """,
        (candidate_id,),
    )


def _endpoint(
    entity_id,
    contact_point_id,
):
    if (
        (entity_id is None)
        == (contact_point_id is None)
    ):
        raise ValueError(
            "endpoint must identify exactly one subject"
        )

    if entity_id is not None:
        return (0, "entity", int(entity_id))

    return (
        1,
        "contact_point",
        int(contact_point_id),
    )


def _candidate_endpoints(candidate):
    left = _endpoint(
        candidate["left_entity_id"],
        candidate["left_contact_point_id"],
    )
    right = _endpoint(
        candidate["right_entity_id"],
        candidate["right_contact_point_id"],
    )

    if left == right:
        raise ValueError(
            "self-relationships are not permitted"
        )

    return left, right


def _canonical_candidate(
    candidate,
    directionality,
):
    left, right = _candidate_endpoints(candidate)

    if (
        directionality == "directed"
        or left <= right
    ):
        return {
            "left_entity_id":
                candidate["left_entity_id"],
            "right_entity_id":
                candidate["right_entity_id"],
            "left_contact_point_id":
                candidate["left_contact_point_id"],
            "right_contact_point_id":
                candidate["right_contact_point_id"],
        }

    return {
        "left_entity_id":
            candidate["right_entity_id"],
        "right_entity_id":
            candidate["left_entity_id"],
        "left_contact_point_id":
            candidate["right_contact_point_id"],
        "right_contact_point_id":
            candidate["left_contact_point_id"],
    }


def _active_relationship(
    db: sqlite3.Connection,
    candidate,
    endpoints,
):
    return db.execute(
        """
        SELECT id
        FROM contact_relationships
        WHERE
            left_entity_id IS ?
        AND right_entity_id IS ?
        AND left_contact_point_id IS ?
        AND right_contact_point_id IS ?
        AND relationship_type=?
        AND lifecycle_status='active'
        ORDER BY id
        LIMIT 1
        """,
        (
            endpoints["left_entity_id"],
            endpoints["right_entity_id"],
            endpoints["left_contact_point_id"],
            endpoints["right_contact_point_id"],
            candidate["correlation_type"],
        ),
    ).fetchone()


def promote_candidate(
    db: sqlite3.Connection,
    candidate_id: int,
    provenance_id: int,
    *,
    evidence_role: str = "supporting",
    evidence_summary: str = "",
) -> PromotionResult:
    candidate = _candidate(
        db,
        candidate_id,
    )

    if not can_promote_candidate(
        candidate["correlation_type"],
        candidate["confidence"],
        candidate["review_status"],
    ):
        raise ValueError(
            "candidate is not eligible for promotion"
        )

    definition = relationship_definition(
        candidate["correlation_type"]
    )

    endpoints = _canonical_candidate(
        candidate,
        definition.directionality,
    )

    provenance = db.execute(
        """
        SELECT
            id,
            verification_status
        FROM provenance_records
        WHERE id=?
        """,
        (provenance_id,),
    ).fetchone()

    if provenance is None:
        raise ValueError(
            f"provenance not found: {provenance_id}"
        )

    confidence = promotion_confidence(
        candidate["confidence"],
        provenance["verification_status"],
    )

    validate_relationship(
        candidate["correlation_type"],
        confidence,
        definition.directionality,
        candidate=False,
    )

    existing = _active_relationship(
        db,
        candidate,
        endpoints,
    )

    if existing is None:
        cur = db.execute(
            """
            INSERT INTO contact_relationships(
                left_entity_id,
                right_entity_id,
                left_contact_point_id,
                right_contact_point_id,
                relationship_type,
                confidence,
                lifecycle_status,
                directionality,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                endpoints["left_entity_id"],
                endpoints["right_entity_id"],
                endpoints["left_contact_point_id"],
                endpoints["right_contact_point_id"],
                candidate["correlation_type"],
                confidence,
                "active",
                definition.directionality,
                (
                    "Promoted from accepted candidate "
                    + str(candidate_id)
                ),
            ),
        )

        relationship_id = cur.lastrowid
        relationship_created = True

    else:
        relationship_id = existing["id"]
        relationship_created = False

    before = db.total_changes

    db.execute(
        """
        INSERT OR IGNORE INTO relationship_evidence(
            relationship_id,
            provenance_id,
            evidence_role,
            evidence_summary
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            relationship_id,
            provenance_id,
            evidence_role,
            evidence_summary,
        ),
    )

    evidence_created = (
        db.total_changes > before
    )

    return PromotionResult(
        candidate_id=candidate_id,
        relationship_id=relationship_id,
        relationship_created=relationship_created,
        evidence_created=evidence_created,
    )
