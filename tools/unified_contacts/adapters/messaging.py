"""Messaging identity source adapter.

This module extracts candidates only. It does not write to SQLite and
does not merge identities.
"""

import json
from pathlib import Path

from .base import (
    AliasCandidate,
    AttestationCandidate,
    CandidateManifest,
    ContactPointCandidate,
    EntityCandidate,
    ProvenanceCandidate,
    RelationshipCandidate,
)


EXTRACTION_METHOD = "messaging_identity_registry_adapter_v1"


def normalize_email(value):
    value = str(value).strip().lower()

    if (
        not value
        or "@" not in value
        or value.startswith("@")
        or value.endswith("@")
    ):
        raise ValueError(
            f"invalid email address: {value!r}"
        )

    return value


def normalize_domain(value):
    value = str(value).strip().lower().rstrip(".")

    if not value or "." not in value:
        raise ValueError(
            f"invalid domain: {value!r}"
        )

    return value


def _entity_key(name):
    return "organization:" + " ".join(
        str(name).strip().lower().split()
    )


def _email_key(address):
    return "email:" + normalize_email(address)


def _domain_key(domain):
    return "domain:" + normalize_domain(domain)


def extract(
    identities_path,
    inventory_path,
):
    identities_path = Path(identities_path)
    inventory_path = Path(inventory_path)

    identities = json.loads(
        identities_path.read_text()
    )

    inventory = json.loads(
        inventory_path.read_text()
    )

    entities = {}
    points = {}
    relationships = {}
    aliases = {}
    attestations = {}
    review = []

    provenance = (
        ProvenanceCandidate(
            source_kind="register",
            source_name="Edge1 Messaging Identity Registry",
            source_reference=str(identities_path),
            extraction_method=EXTRACTION_METHOD,
            verification_status="document_sourced",
        ),
        ProvenanceCandidate(
            source_kind="register",
            source_name="Edge1 Mail Provider Inventory",
            source_reference=str(inventory_path),
            extraction_method=EXTRACTION_METHOD,
            verification_status="document_sourced",
        ),
    )

    def add_entity(
        name,
        source_path,
        verification="document_sourced",
        identity_role="explicit",
        entity_type="organization",
    ):
        name = str(name).strip()

        if not name:
            return None

        if entity_type == "organization":
            key = _entity_key(name)
        elif entity_type == "person":
            key = "person:" + " ".join(
                name.lower().split()
            )
        else:
            raise ValueError(
                f"unsupported entity type: {entity_type}"
            )

        candidate = EntityCandidate(
            source_key=key,
            entity_type=entity_type,
            canonical_name=name,
            display_name=name,
            verification_hint=verification,
            source_path=source_path,
            identity_role=identity_role,
        )

        existing = entities.get(key)

        if existing is None:
            entities[key] = candidate
        elif (
            existing.entity_type != candidate.entity_type
            or existing.canonical_name.casefold()
            != candidate.canonical_name.casefold()
        ):
            review.append({
                "type": "entity_identity_conflict",
                "source_key": key,
                "existing": existing.__dict__,
                "candidate": candidate.__dict__,
            })

        attestation_key = (
            key,
            "identity_name",
            name.casefold(),
            source_path,
        )

        attestations[attestation_key] = (
            AttestationCandidate(
                subject_key=key,
                attribute="identity_name",
                value=name,
                source_path=source_path,
                verification_hint=verification,
                classification=identity_role,
            )
        )

        return key

    def add_email(
        address,
        classification,
        source_path,
        verification="document_sourced",
    ):
        address = normalize_email(address)
        key = _email_key(address)

        candidate = ContactPointCandidate(
            source_key=key,
            point_type="email",
            normalized_value=address,
            display_value=address,
            classification=classification,
            source_path=source_path,
            verification_hint=verification,
        )

        existing = points.get(key)

        if existing is None:
            points[key] = candidate
        elif (
            existing.point_type != candidate.point_type
            or existing.normalized_value
            != candidate.normalized_value
        ):
            review.append({
                "type": "contact_point_identity_conflict",
                "source_key": key,
                "existing": existing.__dict__,
                "candidate": candidate.__dict__,
            })

        attestation_key = (
            key,
            classification,
            verification,
            source_path,
        )

        attestations[attestation_key] = (
            AttestationCandidate(
                subject_key=key,
                attribute="email_classification",
                value=address,
                source_path=source_path,
                verification_hint=verification,
                classification=classification,
            )
        )

        return key

    def add_domain(
        domain,
        source_path,
        verification="document_sourced",
    ):
        domain = normalize_domain(domain)
        key = _domain_key(domain)

        candidate = ContactPointCandidate(
            source_key=key,
            point_type="domain",
            normalized_value=domain,
            display_value=domain,
            classification="managed_domain",
            source_path=source_path,
            verification_hint=verification,
        )

        existing = points.get(key)

        if existing is None:
            points[key] = candidate
        elif (
            existing.point_type != candidate.point_type
            or existing.normalized_value
            != candidate.normalized_value
        ):
            review.append({
                "type": "contact_point_identity_conflict",
                "source_key": key,
                "existing": existing.__dict__,
                "candidate": candidate.__dict__,
            })

        attestation_key = (
            key,
            "managed_domain",
            verification,
            source_path,
        )

        attestations[attestation_key] = (
            AttestationCandidate(
                subject_key=key,
                attribute="domain_classification",
                value=domain,
                source_path=source_path,
                verification_hint=verification,
                classification="managed_domain",
            )
        )

        return key

    def add_relationship(
        entity_key,
        point_key,
        relationship_type,
        confidence,
        source_path,
    ):
        if not entity_key or not point_key:
            return

        key = (
            entity_key,
            point_key,
            relationship_type,
        )

        candidate = RelationshipCandidate(
            source_entity_key=entity_key,
            source_point_key=point_key,
            relationship_type=relationship_type,
            confidence=confidence,
            source_path=source_path,
        )

        relationships[key] = candidate

    # Domain registry:
    # legal_name establishes the legal organization candidate.
    # operating_name is retained as an alias candidate and is NOT
    # automatically converted into a second entity or merged entity.
    for domain, record in identities.get(
        "domains",
        {},
    ).items():

        base = f"$.domains.{domain}"

        legal_name = str(
            record.get("legal_name", "")
        ).strip()

        operating_name = str(
            record.get("operating_name", "")
        ).strip()

        if not legal_name:
            review.append({
                "type": "domain_missing_legal_name",
                "domain": domain,
                "source_path": base,
            })
            continue

        entity_key = add_entity(
            legal_name,
            base + ".legal_name",
        )

        domain_key = add_domain(
            domain,
            base,
        )

        add_relationship(
            entity_key,
            domain_key,
            "domain",
            "document_sourced",
            base,
        )

        if (
            operating_name
            and operating_name.casefold()
            != legal_name.casefold()
        ):
            alias_key = (
                entity_key,
                operating_name.casefold(),
            )

            aliases[alias_key] = AliasCandidate(
                legal_entity_key=entity_key,
                alias_name=operating_name,
                alias_type="operating_name",
                source_path=base + ".operating_name",
            )

    # Sender profiles explicitly state an address, display name and
    # organization. We extract that assertion without assuming that an
    # organization string matching an operating alias is necessarily the
    # same legal entity.
    for profile_id, profile in identities.get(
        "sender_profiles",
        {},
    ).items():

        base = (
            "$.sender_profiles."
            + profile_id
        )

        address = str(
            profile.get("address", "")
        ).strip()

        organization = str(
            profile.get("organization", "")
        ).strip()

        display_name = str(
            profile.get("display_name", "")
        ).strip()

        address_class = str(
            profile.get(
                "address_class",
                "email",
            )
        ).strip() or "email"

        if not address:
            continue

        point_key = add_email(
            address,
            address_class,
            base + ".address",
        )

        if organization:
            entity_key = add_entity(
                organization,
                base + ".organization",
                identity_role="source_named_organization",
            )

            add_relationship(
                entity_key,
                point_key,
                "email",
                "document_sourced",
                base,
            )

        if (
            display_name
            and organization
            and display_name.casefold()
            != organization.casefold()
        ):
            if address_class.startswith("private_"):
                person_key = add_entity(
                    display_name,
                    base + ".display_name",
                    verification="document_sourced",
                    identity_role="named_person",
                    entity_type="person",
                )

                add_relationship(
                    person_key,
                    point_key,
                    "email",
                    "document_sourced",
                    base,
                )

                review.append({
                    "type": "person_organization_context",
                    "profile_id": profile_id,
                    "person": display_name,
                    "organization": organization,
                    "email": normalize_email(address),
                    "source_path": base,
                    "reason": (
                        "Person and organization are both "
                        "explicitly named. No employment, "
                        "ownership, or organizational identity "
                        "merge is inferred."
                    ),
                })
            else:
                review.append({
                    "type": "role_display_name_context",
                "profile_id": profile_id,
                "display_name": display_name,
                "organization": organization,
                "email": normalize_email(address),
                "source_path": base,
                "reason": (
                    "Display name may identify a role, brand, "
                    "department, or organization. No separate "
                    "canonical identity is inferred."
                ),
            })

    # Provider inventory addresses are observations/evidence candidates,
    # not ownership assertions unless the identity registry separately
    # establishes ownership.
    for domain, record in inventory.get(
        "domains",
        {},
    ).items():

        base = f"$.domains.{domain}"

        admin = record.get(
            "provider_admin_inventory",
            {},
        )

        for index, mailbox in enumerate(
            admin.get(
                "physical_mailboxes",
                [],
            )
        ):
            address = str(
                mailbox.get("address", "")
            ).strip()

            if address:
                add_email(
                    address,
                    "provider_physical_mailbox",
                    (
                        base
                        + ".provider_admin_inventory"
                        + f".physical_mailboxes[{index}].address"
                    ),
                    verification="document_sourced",
                )

        for address in record.get(
            "verified_round_trip_addresses",
            [],
        ):
            add_email(
                address,
                "verified_round_trip",
                base + ".verified_round_trip_addresses",
                verification="document_sourced",
            )

        for address in record.get(
            "configured_but_unverified_addresses",
            [],
        ):
            add_email(
                address,
                "configured_unverified",
                base + ".configured_but_unverified_addresses",
                verification="unverified",
            )

        for address in record.get(
            "observed_but_unregistered_addresses",
            [],
        ):
            add_email(
                address,
                "observed_unregistered",
                base + ".observed_but_unregistered_addresses",
                verification="unverified",
            )

    return CandidateManifest(
        entities=tuple(
            sorted(
                entities.values(),
                key=lambda item: item.source_key,
            )
        ),
        contact_points=tuple(
            sorted(
                points.values(),
                key=lambda item: item.source_key,
            )
        ),
        relationships=tuple(
            sorted(
                relationships.values(),
                key=lambda item: (
                    item.source_entity_key,
                    item.source_point_key,
                    item.relationship_type,
                ),
            )
        ),
        provenance=provenance,
        aliases=tuple(
            sorted(
                aliases.values(),
                key=lambda item: (
                    item.legal_entity_key,
                    item.alias_name.casefold(),
                ),
            )
        ),
        attestations=tuple(
            sorted(
                attestations.values(),
                key=lambda item: (
                    item.subject_key,
                    item.attribute,
                    item.source_path,
                ),
            )
        ),
        review_items=tuple(review),
    )
