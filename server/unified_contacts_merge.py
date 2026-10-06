from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


class ContactMergeError(RuntimeError):
    pass


@dataclass(frozen=True)
class MergePreview:
    survivor_entity_id: int
    absorbed_entity_id: int
    survivor_name: str
    absorbed_name: str
    survivor_type: str
    absorbed_type: str
    assertions_to_move: int
    assertion_collisions: int
    aliases_to_preserve: int
    attestations_to_move: int
    relationships_to_repoint: int
    correlations_to_repoint: int = 0


@dataclass(frozen=True)
class MergeResult:
    survivor_entity_id: int
    absorbed_entity_id: int
    assertions_moved: int
    assertions_reconciled: int
    aliases_preserved: int
    attestations_moved: int
    relationships_repointed: int
    absorbed_lifecycle: str
    correlations_repointed: int = 0


class UnifiedContactsMerge:
    def __init__(self, database: str | Path):
        self.database = str(database)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.database)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    @staticmethod
    def _entity(
        con: sqlite3.Connection,
        entity_id: int,
    ) -> sqlite3.Row:
        row = con.execute(
            """
            SELECT *
            FROM contact_entities
            WHERE id=?
            """,
            (entity_id,),
        ).fetchone()

        if row is None:
            raise ContactMergeError(
                f"Contact entity {entity_id} does not exist."
            )

        return row

    @staticmethod
    def _assertion_semantics(row: sqlite3.Row):
        return (
            row["confidence"],
            row["valid_from"],
            row["valid_to"],
            row["notes"],
        )

    @staticmethod
    def _former_names(
        survivor: sqlite3.Row,
        absorbed: sqlite3.Row,
    ) -> list[str]:
        survivor_names = {
            value.strip()
            for value in (
                survivor["canonical_name"],
                survivor["display_name"],
            )
            if isinstance(value, str) and value.strip()
        }

        names: list[str] = []

        for value in (
            absorbed["canonical_name"],
            absorbed["display_name"],
        ):
            if not isinstance(value, str):
                continue

            value = value.strip()

            if not value:
                continue

            if value in survivor_names:
                continue

            if value not in names:
                names.append(value)

        return names

    @staticmethod
    def _ambiguous_entity_pair(
        con: sqlite3.Connection,
        table: str,
        survivor_entity_id: int,
        absorbed_entity_id: int,
    ) -> bool:
        row = con.execute(
            f"""
            SELECT 1
            FROM {table}
            WHERE (
                left_entity_id=?
                AND right_entity_id=?
            )
            OR (
                left_entity_id=?
                AND right_entity_id=?
            )
            LIMIT 1
            """,
            (
                survivor_entity_id,
                absorbed_entity_id,
                absorbed_entity_id,
                survivor_entity_id,
            ),
        ).fetchone()

        return row is not None

    def preview(
        self,
        survivor_entity_id: int,
        absorbed_entity_id: int,
    ) -> MergePreview:
        if survivor_entity_id == absorbed_entity_id:
            raise ContactMergeError(
                "A contact cannot be merged into itself."
            )

        with self._connect() as con:
            survivor = self._entity(
                con,
                survivor_entity_id,
            )

            absorbed = self._entity(
                con,
                absorbed_entity_id,
            )

            if (
                survivor["entity_type"]
                != absorbed["entity_type"]
            ):
                raise ContactMergeError(
                    "Person and organization contacts cannot "
                    "be merged without an explicit type "
                    "resolution."
                )

            assertions = con.execute(
                """
                SELECT *
                FROM contact_assertions
                WHERE entity_id=?
                ORDER BY id
                """,
                (absorbed_entity_id,),
            ).fetchall()

            collisions = 0

            for assertion in assertions:
                collision = con.execute(
                    """
                    SELECT 1
                    FROM contact_assertions
                    WHERE entity_id=?
                      AND contact_point_id=?
                      AND assertion_type=?
                    LIMIT 1
                    """,
                    (
                        survivor_entity_id,
                        assertion["contact_point_id"],
                        assertion["assertion_type"],
                    ),
                ).fetchone()

                collisions += int(
                    collision is not None
                )

            aliases_to_preserve = 0

            for name in self._former_names(
                survivor,
                absorbed,
            ):
                existing = con.execute(
                    """
                    SELECT 1
                    FROM contact_entity_aliases
                    WHERE entity_id=?
                      AND alias_name=?
                      AND alias_type='former_name'
                    LIMIT 1
                    """,
                    (
                        survivor_entity_id,
                        name,
                    ),
                ).fetchone()

                if existing is None:
                    aliases_to_preserve += 1

            relationships = con.execute(
                """
                SELECT COUNT(*)
                FROM contact_relationships
                WHERE left_entity_id=?
                   OR right_entity_id=?
                """,
                (
                    absorbed_entity_id,
                    absorbed_entity_id,
                ),
            ).fetchone()[0]

            correlations = con.execute(
                """
                SELECT COUNT(*)
                FROM candidate_correlations
                WHERE left_entity_id=?
                   OR right_entity_id=?
                """,
                (
                    absorbed_entity_id,
                    absorbed_entity_id,
                ),
            ).fetchone()[0]

            return MergePreview(
                survivor_entity_id=survivor_entity_id,
                absorbed_entity_id=absorbed_entity_id,
                survivor_name=survivor[
                    "canonical_name"
                ],
                absorbed_name=absorbed[
                    "canonical_name"
                ],
                survivor_type=survivor[
                    "entity_type"
                ],
                absorbed_type=absorbed[
                    "entity_type"
                ],
                assertions_to_move=len(assertions),
                assertion_collisions=collisions,
                aliases_to_preserve=(
                    aliases_to_preserve
                ),

                # Entity-level attestations remain attached
                # to the absorbed tombstone as historical
                # identity evidence.
                attestations_to_move=0,

                relationships_to_repoint=relationships,
                correlations_to_repoint=correlations,
            )

    def merge(
        self,
        survivor_entity_id: int,
        absorbed_entity_id: int,
        *,
        merged_by: str = "edge1.contacts.manage",
    ) -> MergeResult:
        if survivor_entity_id == absorbed_entity_id:
            raise ContactMergeError(
                "A contact cannot be merged into itself."
            )

        if not isinstance(merged_by, str):
            raise ContactMergeError(
                "Merge actor is invalid."
            )

        merged_by = merged_by.strip()

        if not merged_by:
            raise ContactMergeError(
                "Merge actor is required."
            )

        con = self._connect()

        try:
            con.execute("BEGIN IMMEDIATE")

            survivor = self._entity(
                con,
                survivor_entity_id,
            )

            absorbed = self._entity(
                con,
                absorbed_entity_id,
            )

            if (
                survivor["entity_type"]
                != absorbed["entity_type"]
            ):
                raise ContactMergeError(
                    "Person and organization contacts "
                    "cannot be merged without an explicit "
                    "type resolution."
                )

            if (
                survivor["lifecycle_status"]
                != "active"
            ):
                raise ContactMergeError(
                    "Surviving contact must be active."
                )

            if (
                absorbed["lifecycle_status"]
                == "retired"
            ):
                raise ContactMergeError(
                    "Absorbed contact is already retired."
                )

            already_merged = con.execute(
                """
                SELECT survivor_entity_id
                FROM contact_entity_merges
                WHERE absorbed_entity_id=?
                LIMIT 1
                """,
                (absorbed_entity_id,),
            ).fetchone()

            if already_merged is not None:
                raise ContactMergeError(
                    "Absorbed contact already has a "
                    "recorded merge."
                )

            #
            # Relationship/correlation pairs directly
            # connecting survivor and absorbed would become
            # self-references. Their meaning is ambiguous,
            # so require explicit resolution instead of
            # silently rewriting them.
            #
            if self._ambiguous_entity_pair(
                con,
                "contact_relationships",
                survivor_entity_id,
                absorbed_entity_id,
            ):
                raise ContactMergeError(
                    "Merge would create a self-relationship; "
                    "resolve the relationship first."
                )

            if self._ambiguous_entity_pair(
                con,
                "candidate_correlations",
                survivor_entity_id,
                absorbed_entity_id,
            ):
                raise ContactMergeError(
                    "Merge would create a self-correlation; "
                    "resolve the correlation first."
                )

            #
            # Dedicated merge provenance is created before
            # dependent records so former-name aliases can
            # point directly at the decision that created
            # them.
            #
            provenance_cur = con.execute(
                """
                INSERT INTO provenance_records (
                    source_kind,
                    source_name,
                    source_reference,
                    extraction_method,
                    verification_status,
                    notes
                )
                VALUES (
                    'manual',
                    'Edge1 Contacts',
                    'entity.merge',
                    'manual_operator',
                    'unverified',
                    ?
                )
                """,
                (
                    (
                        "Explicit operator merge of entity "
                        f"{absorbed_entity_id} into "
                        f"{survivor_entity_id}."
                    ),
                ),
            )

            merge_provenance_id = int(
                provenance_cur.lastrowid
            )

            aliases_preserved = 0

            for name in self._former_names(
                survivor,
                absorbed,
            ):
                existing = con.execute(
                    """
                    SELECT 1
                    FROM contact_entity_aliases
                    WHERE entity_id=?
                      AND alias_name=?
                      AND alias_type='former_name'
                    LIMIT 1
                    """,
                    (
                        survivor_entity_id,
                        name,
                    ),
                ).fetchone()

                if existing is not None:
                    continue

                con.execute(
                    """
                    INSERT INTO contact_entity_aliases (
                        entity_id,
                        alias_name,
                        alias_type,
                        confidence,
                        provenance_id,
                        source_path,
                        notes
                    )
                    VALUES (
                        ?,
                        ?,
                        'former_name',
                        'unverified',
                        ?,
                        'edge1://contacts/merge',
                        ?
                    )
                    """,
                    (
                        survivor_entity_id,
                        name,
                        merge_provenance_id,
                        (
                            "Preserved from absorbed entity "
                            f"{absorbed_entity_id} during "
                            "guarded merge into entity "
                            f"{survivor_entity_id}."
                        ),
                    ),
                )

                aliases_preserved += 1

            #
            # Assertions preserve their temporal state.
            #
            # Because the schema permits only one assertion
            # per entity/contact-point/type, a collision can
            # be reconciled only when all assertion semantics
            # are identical. If current/historical state,
            # confidence or notes differ, abort rather than
            # erase evidence.
            #
            assertions = con.execute(
                """
                SELECT *
                FROM contact_assertions
                WHERE entity_id=?
                ORDER BY id
                """,
                (absorbed_entity_id,),
            ).fetchall()

            assertions_moved = 0
            assertions_reconciled = 0

            for assertion in assertions:
                collision = con.execute(
                    """
                    SELECT *
                    FROM contact_assertions
                    WHERE entity_id=?
                      AND contact_point_id=?
                      AND assertion_type=?
                    LIMIT 1
                    """,
                    (
                        survivor_entity_id,
                        assertion["contact_point_id"],
                        assertion["assertion_type"],
                    ),
                ).fetchone()

                if collision is None:
                    con.execute(
                        """
                        UPDATE contact_assertions
                        SET entity_id=?,
                            updated_at=CURRENT_TIMESTAMP
                        WHERE id=?
                        """,
                        (
                            survivor_entity_id,
                            assertion["id"],
                        ),
                    )

                    assertions_moved += 1
                    continue

                if (
                    self._assertion_semantics(
                        assertion
                    )
                    != self._assertion_semantics(
                        collision
                    )
                ):
                    raise ContactMergeError(
                        "Assertion collision has different "
                        "temporal or evidentiary semantics "
                        f"for contact point "
                        f"{assertion['contact_point_id']}."
                    )

                evidence = con.execute(
                    """
                    SELECT *
                    FROM assertion_evidence
                    WHERE assertion_id=?
                    """,
                    (assertion["id"],),
                ).fetchall()

                for ev in evidence:
                    existing_ev = con.execute(
                        """
                        SELECT 1
                        FROM assertion_evidence
                        WHERE assertion_id=?
                          AND provenance_id=?
                          AND evidence_role=?
                          AND (
                              evidence_summary IS ?
                              OR evidence_summary=?
                          )
                        LIMIT 1
                        """,
                        (
                            collision["id"],
                            ev["provenance_id"],
                            ev["evidence_role"],
                            ev["evidence_summary"],
                            ev["evidence_summary"],
                        ),
                    ).fetchone()

                    if existing_ev is None:
                        con.execute(
                            """
                            INSERT INTO assertion_evidence (
                                assertion_id,
                                provenance_id,
                                evidence_role,
                                evidence_summary
                            )
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                collision["id"],
                                ev["provenance_id"],
                                ev["evidence_role"],
                                ev["evidence_summary"],
                            ),
                        )

                con.execute(
                    """
                    DELETE FROM contact_assertions
                    WHERE id=?
                    """,
                    (assertion["id"],),
                )

                assertions_reconciled += 1

            #
            # IMPORTANT:
            # Direct entity attestations are intentionally
            # NOT moved. They document the historical
            # absorbed identity and remain attached to the
            # retired tombstone.
            #
            attestations_moved = 0

            try:
                left_count = con.execute(
                    """
                    UPDATE contact_relationships
                    SET left_entity_id=?,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE left_entity_id=?
                    """,
                    (
                        survivor_entity_id,
                        absorbed_entity_id,
                    ),
                ).rowcount

                right_count = con.execute(
                    """
                    UPDATE contact_relationships
                    SET right_entity_id=?,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE right_entity_id=?
                    """,
                    (
                        survivor_entity_id,
                        absorbed_entity_id,
                    ),
                ).rowcount

            except sqlite3.IntegrityError as exc:
                raise ContactMergeError(
                    "Relationship repointing would create "
                    "a duplicate active relationship."
                ) from exc

            correlation_left = con.execute(
                """
                UPDATE candidate_correlations
                SET left_entity_id=?
                WHERE left_entity_id=?
                """,
                (
                    survivor_entity_id,
                    absorbed_entity_id,
                ),
            ).rowcount

            correlation_right = con.execute(
                """
                UPDATE candidate_correlations
                SET right_entity_id=?
                WHERE right_entity_id=?
                """,
                (
                    survivor_entity_id,
                    absorbed_entity_id,
                ),
            ).rowcount

            con.execute(
                """
                INSERT INTO contact_entity_merges (
                    absorbed_entity_id,
                    survivor_entity_id,
                    provenance_id,
                    reason,
                    merged_by
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    absorbed_entity_id,
                    survivor_entity_id,
                    merge_provenance_id,
                    "Explicit operator contact merge.",
                    merged_by,
                ),
            )

            merge_note = (
                f"Merged into contact entity "
                f"{survivor_entity_id}."
            )

            existing_notes = (
                absorbed["notes"] or ""
            ).strip()

            if merge_note in existing_notes:
                notes = existing_notes
            elif existing_notes:
                notes = (
                    existing_notes.rstrip()
                    + " "
                    + merge_note
                )
            else:
                notes = merge_note

            con.execute(
                """
                UPDATE contact_entities
                SET lifecycle_status='retired',
                    notes=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    notes,
                    absorbed_entity_id,
                ),
            )

            fk_errors = con.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            if fk_errors:
                raise ContactMergeError(
                    "Foreign-key verification failed "
                    "during contact merge."
                )

            con.commit()

            return MergeResult(
                survivor_entity_id=survivor_entity_id,
                absorbed_entity_id=absorbed_entity_id,
                assertions_moved=assertions_moved,
                assertions_reconciled=(
                    assertions_reconciled
                ),
                aliases_preserved=aliases_preserved,
                attestations_moved=attestations_moved,
                relationships_repointed=(
                    left_count + right_count
                ),
                absorbed_lifecycle="retired",
                correlations_repointed=(
                    correlation_left
                    + correlation_right
                ),
            )

        except ContactMergeError:
            con.rollback()
            raise

        except sqlite3.IntegrityError as exc:
            con.rollback()
            raise ContactMergeError(
                "Contact merge would violate an "
                "identity or dependency constraint."
            ) from exc

        except Exception:
            con.rollback()
            raise

        finally:
            con.close()
