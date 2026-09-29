from dataclasses import dataclass


@dataclass(frozen=True)
class RelationshipDefinition:
    name: str
    directionality: str
    category: str
    durable: bool
    candidate_only: bool
    description: str


RELATIONSHIP_DEFINITIONS = {
    "works_for": RelationshipDefinition(
        name="works_for",
        directionality="directed",
        category="organizational",
        durable=True,
        candidate_only=False,
        description=(
            "A person works for an organization."
        ),
    ),

    "operates_as": RelationshipDefinition(
        name="operates_as",
        directionality="directed",
        category="organizational",
        durable=True,
        candidate_only=False,
        description=(
            "An entity operates using another "
            "business or organizational identity."
        ),
    ),

    "vendor_of": RelationshipDefinition(
        name="vendor_of",
        directionality="directed",
        category="commercial",
        durable=True,
        candidate_only=False,
        description=(
            "An entity supplies goods or services "
            "to another entity."
        ),
    ),

    "member_of": RelationshipDefinition(
        name="member_of",
        directionality="directed",
        category="organizational",
        durable=True,
        candidate_only=False,
        description=(
            "A person or organization is a member "
            "of another organization."
        ),
    ),

    "associated_project": RelationshipDefinition(
        name="associated_project",
        directionality="undirected",
        category="context",
        durable=True,
        candidate_only=False,
        description=(
            "Two subjects are associated through "
            "a documented project."
        ),
    ),

    "communicated_with": RelationshipDefinition(
        name="communicated_with",
        directionality="undirected",
        category="interaction",
        durable=True,
        candidate_only=False,
        description=(
            "Documented communication occurred "
            "between two subjects."
        ),
    ),

    "same_document": RelationshipDefinition(
        name="same_document",
        directionality="undirected",
        category="context",
        durable=True,
        candidate_only=False,
        description=(
            "Two subjects co-occur in the same "
            "source document. This does not imply "
            "identity or another relationship."
        ),
    ),

    "shared_address": RelationshipDefinition(
        name="shared_address",
        directionality="undirected",
        category="context",
        durable=True,
        candidate_only=False,
        description=(
            "Two subjects are independently "
            "associated with the same physical "
            "address."
        ),
    ),

    "shared_contact_point": RelationshipDefinition(
        name="shared_contact_point",
        directionality="undirected",
        category="context",
        durable=True,
        candidate_only=False,
        description=(
            "Two entities are independently "
            "asserted to the same contact point. "
            "This does not imply identity."
        ),
    ),

    "associated_with": RelationshipDefinition(
        name="associated_with",
        directionality="undirected",
        category="general",
        durable=True,
        candidate_only=False,
        description=(
            "A documented association exists when "
            "a more specific relationship type "
            "cannot yet be used."
        ),
    ),

    "possible_match": RelationshipDefinition(
        name="possible_match",
        directionality="undirected",
        category="correlation",
        durable=False,
        candidate_only=True,
        description=(
            "Two subjects may represent the same "
            "real-world identity. Review is "
            "required; this never merges them."
        ),
    ),
}


DURABLE_CONFIDENCE = {
    "confirmed",
    "document_sourced",
    "probable",
    "unverified",
    "disputed",
}


CANDIDATE_CONFIDENCE = {
    "probable",
    "possible",
    "unverified",
    "disputed",
}


PROMOTABLE_REVIEW_STATUS = {
    "accepted",
}


def relationship_definition(name):
    try:
        return RELATIONSHIP_DEFINITIONS[name]
    except KeyError as exc:
        raise ValueError(
            f"unknown relationship type: {name}"
        ) from exc


def validate_relationship(
    relationship_type,
    confidence,
    directionality,
    *,
    candidate=False,
):
    definition = relationship_definition(
        relationship_type
    )

    if directionality != definition.directionality:
        raise ValueError(
            "relationship directionality does not "
            "match policy"
        )

    allowed = (
        CANDIDATE_CONFIDENCE
        if candidate
        else DURABLE_CONFIDENCE
    )

    if confidence not in allowed:
        raise ValueError(
            "invalid confidence for relationship"
        )

    if candidate:
        return True

    if definition.candidate_only:
        raise ValueError(
            "candidate-only relationship cannot "
            "be persisted as durable"
        )

    if not definition.durable:
        raise ValueError(
            "relationship is not durable"
        )

    return True


def can_promote_candidate(
    relationship_type,
    confidence,
    review_status,
):
    definition = relationship_definition(
        relationship_type
    )

    if definition.candidate_only:
        return False

    if review_status not in PROMOTABLE_REVIEW_STATUS:
        return False

    if confidence not in CANDIDATE_CONFIDENCE:
        return False

    return True


def promotion_confidence(
    candidate_confidence,
    *,
    evidence_verified=False,
    evidence_document_sourced=False,
):
    if evidence_verified:
        return "confirmed"

    if evidence_document_sourced:
        return "document_sourced"

    if candidate_confidence == "probable":
        return "probable"

    return "unverified"
