from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from tools.unified_contacts.identity_gate import match_entity


ENTITY_TYPES = {"person", "organization"}

POINT_TYPES = {
    "phone",
    "fax",
    "email",
    "website",
    "domain",
    "postal",
}

ENTITY_LIFECYCLES = {"active", "inactive", "unknown", "retired"}

POINT_LIFECYCLES = {
    "active",
    "archived",
}

VERIFICATION_STATUSES = {
    "verified",
    "document_sourced",
    "unverified",
    "disputed",
}

ASSERTION_CONFIDENCE = {
    "confirmed",
    "document_sourced",
    "probable",
    "unverified",
    "disputed",
}


class ContactsCrudError(ValueError):
    pass


class ContactsNotFound(ContactsCrudError):
    pass


class ContactsConflict(ContactsCrudError):
    pass


@dataclass(frozen=True)
class CrudResult:
    operation: str
    entity_id: int | None = None
    contact_point_id: int | None = None
    assertion_id: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "entity_id": self.entity_id,
            "contact_point_id": self.contact_point_id,
            "assertion_id": self.assertion_id,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def required_text(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise ContactsCrudError(f"{name} must be text")

    value = value.strip()

    if not value:
        raise ContactsCrudError(f"{name} is required")

    return value


def optional_text(name: str, value: Any) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ContactsCrudError(f"{name} must be text")

    value = value.strip()
    return value or None


def enum_value(
    name: str,
    value: Any,
    allowed: set[str],
) -> str:
    value = required_text(name, value)

    if value not in allowed:
        raise ContactsCrudError(
            f"{name} is not an allowed value"
        )

    return value


def normalize_contact_point(
    point_type: str,
    value: Any,
) -> tuple[str, str]:
    display = required_text("value", value)

    if point_type in {"phone", "fax"}:
        digits = re.sub(r"\D", "", display)

        if len(digits) == 10:
            normalized = "+1" + digits
        elif len(digits) == 11 and digits.startswith("1"):
            normalized = "+" + digits
        elif display.startswith("+") and 8 <= len(digits) <= 15:
            normalized = "+" + digits
        else:
            raise ContactsCrudError(
                "phone/fax value cannot be normalized"
            )

        return normalized, display

    if point_type == "email":
        normalized = display.casefold()

        if (
            "@" not in normalized
            or normalized.startswith("@")
            or normalized.endswith("@")
        ):
            raise ContactsCrudError(
                "email value is invalid"
            )

        return normalized, display

    if point_type == "domain":
        normalized = display.casefold().rstrip(".")

        if not normalized or " " in normalized:
            raise ContactsCrudError(
                "domain value is invalid"
            )

        return normalized, display

    if point_type == "website":
        normalized = display.strip()

        if not (
            normalized.startswith("https://")
            or normalized.startswith("http://")
        ):
            raise ContactsCrudError(
                "website must use http:// or https://"
            )

        return normalized, display

    # Postal/address data must not be destructively normalized.
    return display, display


class UnifiedContactsCrud:
    def __init__(self, connection: sqlite3.Connection):
        self.db = connection
        self.db.row_factory = sqlite3.Row

    def _entity(self, entity_id: int) -> sqlite3.Row:
        row = self.db.execute(
            """
            SELECT *
            FROM contact_entities
            WHERE id = ?
            """,
            (entity_id,),
        ).fetchone()

        if row is None:
            raise ContactsNotFound("contact entity not found")

        return row

    def _point(self, point_id: int) -> sqlite3.Row:
        row = self.db.execute(
            """
            SELECT *
            FROM contact_points
            WHERE id = ?
            """,
            (point_id,),
        ).fetchone()

        if row is None:
            raise ContactsNotFound(
                "contact point not found"
            )

        return row

    def _manual_provenance(
        self,
        *,
        operation: str,
        entity_id: int | None = None,
        contact_point_id: int | None = None,
        assertion_id: int | None = None,
        attribute: str,
        attested_value: str,
        notes: str | None = None,
    ) -> int:
        """
        Record operator-entered canonical evidence.

        This runs on the caller's existing transaction so
        canonical data and provenance commit or roll back
        together.
        """
        now = utc_now()

        cur = self.db.execute(
            """
            INSERT INTO provenance_records (
                source_kind,
                source_name,
                source_reference,
                extraction_method,
                verification_status,
                notes,
                created_at
            )
            VALUES (
                'manual',
                'Edge1 Contacts',
                ?,
                'manual_operator',
                'unverified',
                ?,
                ?
            )
            """,
            (
                operation,
                notes,
                now,
            ),
        )

        provenance_id = int(cur.lastrowid)

        if assertion_id is not None:
            self.db.execute(
                """
                INSERT OR IGNORE INTO assertion_evidence (
                    assertion_id,
                    provenance_id,
                    evidence_role,
                    evidence_summary,
                    created_at
                )
                VALUES (?, ?, 'supports', ?, ?)
                """,
                (
                    assertion_id,
                    provenance_id,
                    notes or operation,
                    now,
                ),
            )

        # contact_attestations deliberately targets exactly
        # one canonical object. Entity mutations attest the
        # entity; contact-point mutations attest the point.
        # assertion_evidence separately records why an
        # assertion/association is supported.
        if contact_point_id is not None:
            attestation_entity_id = None
            attestation_point_id = contact_point_id
        elif entity_id is not None:
            attestation_entity_id = entity_id
            attestation_point_id = None
        else:
            raise ValueError(
                "manual_provenance_target_required"
            )

        self.db.execute(
            """
            INSERT INTO contact_attestations (
                entity_id,
                contact_point_id,
                provenance_id,
                attribute,
                attested_value,
                classification,
                verification_status,
                source_path,
                notes,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'unverified', ?, ?, ?)
            """,
            (
                attestation_entity_id,
                attestation_point_id,
                provenance_id,
                attribute,
                attested_value,
                'manual_operator',
                'edge1://contacts/manual',
                notes,
                now,
            ),
        )

        return provenance_id

    def create_entity(
        self,
        *,
        entity_type: str,
        canonical_name: str,
        display_name: str | None = None,
        verification_status: str = "unverified",
        notes: str | None = None,
    ) -> CrudResult:
        entity_type = enum_value(
            "entity_type",
            entity_type,
            ENTITY_TYPES,
        )
        canonical_name = required_text(
            "canonical_name",
            canonical_name,
        )
        display_name = optional_text(
            "display_name",
            display_name,
        )
        verification_status = enum_value(
            "verification_status",
            verification_status,
            VERIFICATION_STATUSES,
        )
        notes = optional_text("notes", notes)
        duplicate_check = match_entity(self.db, entity_type, canonical_name)
        if duplicate_check['status'] != 'new':
            raise ContactsConflict(
                'duplicate-prevention gate blocked entity creation: '
                + repr(duplicate_check)
            )
        now = utc_now()

        cur = self.db.execute(
            """
            INSERT INTO contact_entities (
                entity_type,
                canonical_name,
                display_name,
                lifecycle_status,
                verification_status,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'active', ?, ?, ?, ?)
            """,
            (
                entity_type,
                canonical_name,
                display_name,
                verification_status,
                notes,
                now,
                now,
            ),
        )

        return CrudResult(
            operation="entity.create",
            entity_id=int(cur.lastrowid),
        )

    def update_entity(
        self,
        *,
        entity_id: int,
        canonical_name: str,
        display_name: str | None = None,
        verification_status: str,
        notes: str | None = None,
    ) -> CrudResult:
        self._entity(entity_id)

        canonical_name = required_text(
            "canonical_name",
            canonical_name,
        )
        display_name = optional_text(
            "display_name",
            display_name,
        )
        verification_status = enum_value(
            "verification_status",
            verification_status,
            VERIFICATION_STATUSES,
        )
        notes = optional_text("notes", notes)
        duplicate_check = match_entity(
            self.db,
            self._entity(entity_id)['entity_type'],
            canonical_name,
            exclude_entity_id=entity_id,
        )
        if duplicate_check['status'] != 'new':
            raise ContactsConflict(
                'duplicate-prevention gate blocked entity rename/update: '
                + repr(duplicate_check)
            )

        self.db.execute(
            """
            UPDATE contact_entities
            SET canonical_name = ?,
                display_name = ?,
                verification_status = ?,
                notes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                canonical_name,
                display_name,
                verification_status,
                notes,
                utc_now(),
                entity_id,
            ),
        )

        return CrudResult(
            operation="entity.update",
            entity_id=entity_id,
        )

    def set_entity_lifecycle(
        self,
        *,
        entity_id: int,
        lifecycle_status: str,
    ) -> CrudResult:
        self._entity(entity_id)

        lifecycle_status = enum_value(
            "lifecycle_status",
            lifecycle_status,
            ENTITY_LIFECYCLES,
        )

        self.db.execute(
            """
            UPDATE contact_entities
            SET lifecycle_status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                lifecycle_status,
                utc_now(),
                entity_id,
            ),
        )

        return CrudResult(
            operation=f"entity.{lifecycle_status}",
            entity_id=entity_id,
        )

    def add_contact_point(
        self,
        *,
        entity_id: int,
        point_type: str,
        value: str,
        classification: str | None = None,
        confidence: str = "unverified",
        assertion_notes: str | None = None,
    ) -> CrudResult:
        self._entity(entity_id)

        point_type = enum_value(
            "point_type",
            point_type,
            POINT_TYPES,
        )
        confidence = enum_value(
            "confidence",
            confidence,
            ASSERTION_CONFIDENCE,
        )
        classification = optional_text(
            "classification",
            classification,
        )
        assertion_notes = optional_text(
            "assertion_notes",
            assertion_notes,
        )

        normalized, display = normalize_contact_point(
            point_type,
            value,
        )
        now = utc_now()

        point = self.db.execute(
            """
            SELECT id, lifecycle_status
            FROM contact_points
            WHERE point_type = ?
              AND normalized_value = ?
            """,
            (
                point_type,
                normalized,
            ),
        ).fetchone()

        if point is None:
            cur = self.db.execute(
                """
                INSERT INTO contact_points (
                    point_type,
                    normalized_value,
                    display_value,
                    classification,
                    lifecycle_status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    point_type,
                    normalized,
                    display,
                    classification,
                    now,
                    now,
                ),
            )
            point_id = int(cur.lastrowid)
        else:
            point_id = int(point["id"])

            self.db.execute(
                """
                UPDATE contact_points
                SET display_value = ?,
                    classification = COALESCE(
                        ?,
                        classification
                    ),
                    lifecycle_status = 'active',
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    display,
                    classification,
                    now,
                    point_id,
                ),
            )

        existing = self.db.execute(
            """
            SELECT id, valid_to
            FROM contact_assertions
            WHERE entity_id = ?
              AND contact_point_id = ?
              AND assertion_type = 'contact'
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                entity_id,
                point_id,
            ),
        ).fetchone()

        if existing is not None and existing["valid_to"] is None:
            raise ContactsConflict(
                "contact point is already attached "
                "to this entity"
            )

        if existing is not None:
            assertion_id = int(existing["id"])

            self.db.execute(
                """
                UPDATE contact_assertions
                SET confidence = ?,
                    valid_from = ?,
                    valid_to = NULL,
                    notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    confidence,
                    now,
                    assertion_notes,
                    now,
                    assertion_id,
                ),
            )
        else:
            cur = self.db.execute(
                """
                INSERT INTO contact_assertions (
                    entity_id,
                    contact_point_id,
                    assertion_type,
                    confidence,
                    valid_from,
                    valid_to,
                    notes,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, 'contact', ?, ?, NULL, ?, ?, ?)
                """,
                (
                    entity_id,
                    point_id,
                    confidence,
                    now,
                    assertion_notes,
                    now,
                    now,
                ),
            )
            assertion_id = int(cur.lastrowid)

        return CrudResult(
            operation="contact_point.add",
            entity_id=entity_id,
            contact_point_id=point_id,
            assertion_id=assertion_id,
        )

    def update_contact_point(
        self,
        *,
        entity_id: int,
        contact_point_id: int,
        value: str,
        classification: str | None = None,
    ) -> CrudResult:
        self._entity(entity_id)
        point = self._point(contact_point_id)

        owned = self.db.execute(
            """
            SELECT id
            FROM contact_assertions
            WHERE entity_id = ?
              AND contact_point_id = ?
              AND assertion_type = 'contact'
              AND valid_to IS NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                entity_id,
                contact_point_id,
            ),
        ).fetchone()

        if owned is None:
            raise ContactsNotFound(
                "active entity/contact assertion not found"
            )

        normalized, display = normalize_contact_point(
            point["point_type"],
            value,
        )

        # A canonical contact point may be asserted by more than
        # one entity. Never mutate a shared endpoint in place.
        other_active = self.db.execute(
            """
            SELECT COUNT(*)
            FROM contact_assertions
            WHERE contact_point_id = ?
              AND assertion_type = 'contact'
              AND valid_to IS NULL
              AND entity_id <> ?
            """,
            (
                contact_point_id,
                entity_id,
            ),
        ).fetchone()[0]

        if other_active:
            raise ContactsConflict(
                "contact point is shared by another entity; "
                "detach and add the corrected endpoint instead"
            )

        collision = self.db.execute(
            """
            SELECT id
            FROM contact_points
            WHERE point_type = ?
              AND normalized_value = ?
              AND id <> ?
            """,
            (
                point["point_type"],
                normalized,
                contact_point_id,
            ),
        ).fetchone()

        if collision is not None:
            raise ContactsConflict(
                "normalized contact point already exists; "
                "use the existing endpoint instead"
            )

        self.db.execute(
            """
            UPDATE contact_points
            SET normalized_value = ?,
                display_value = ?,
                classification = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                normalized,
                display,
                optional_text(
                    "classification",
                    classification,
                ),
                utc_now(),
                contact_point_id,
            ),
        )

        return CrudResult(
            operation="contact_point.update",
            entity_id=entity_id,
            contact_point_id=contact_point_id,
            assertion_id=int(owned["id"]),
        )

    def detach_contact_point(
        self,
        *,
        entity_id: int,
        contact_point_id: int,
    ) -> CrudResult:
        self._entity(entity_id)
        self._point(contact_point_id)

        row = self.db.execute(
            """
            SELECT id
            FROM contact_assertions
            WHERE entity_id = ?
              AND contact_point_id = ?
              AND assertion_type = 'contact'
              AND valid_to IS NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                entity_id,
                contact_point_id,
            ),
        ).fetchone()

        if row is None:
            raise ContactsNotFound(
                "active entity/contact assertion not found"
            )

        assertion_id = int(row["id"])
        now = utc_now()

        self.db.execute(
            """
            UPDATE contact_assertions
            SET valid_to = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                now,
                now,
                assertion_id,
            ),
        )

        return CrudResult(
            operation="contact_point.detach",
            entity_id=entity_id,
            contact_point_id=contact_point_id,
            assertion_id=assertion_id,
        )
