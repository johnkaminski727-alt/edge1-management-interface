"""Source-neutral candidate records for Unified Contacts adapters."""

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass(frozen=True)
class EntityCandidate:
    source_key: str
    entity_type: str
    canonical_name: str
    display_name: str
    verification_hint: str
    source_path: str
    identity_role: str = "explicit"


@dataclass(frozen=True)
class ContactPointCandidate:
    source_key: str
    point_type: str
    normalized_value: str
    display_value: str
    classification: str
    source_path: str
    verification_hint: str = "unverified"


@dataclass(frozen=True)
class RelationshipCandidate:
    source_entity_key: str
    source_point_key: str
    relationship_type: str
    confidence: str
    source_path: str


@dataclass(frozen=True)
class ProvenanceCandidate:
    source_kind: str
    source_name: str
    source_reference: str
    extraction_method: str
    verification_status: str


@dataclass(frozen=True)
class AttestationCandidate:
    subject_key: str
    attribute: str
    value: str
    source_path: str
    verification_hint: str
    classification: str = ""



@dataclass(frozen=True)
class AliasCandidate:
    legal_entity_key: str
    alias_name: str
    alias_type: str
    source_path: str
    confidence: str = "document_sourced"


@dataclass(frozen=True)
class CandidateManifest:
    entities: tuple
    contact_points: tuple
    relationships: tuple
    provenance: tuple
    aliases: tuple
    attestations: tuple
    review_items: tuple

    def as_dict(self):
        return {
            "entities": [
                asdict(item)
                for item in self.entities
            ],
            "contact_points": [
                asdict(item)
                for item in self.contact_points
            ],
            "relationships": [
                asdict(item)
                for item in self.relationships
            ],
            "provenance": [
                asdict(item)
                for item in self.provenance
            ],
            "aliases": [
                asdict(item)
                for item in self.aliases
            ],
            "attestations": [
                asdict(item)
                for item in self.attestations
            ],
            "review_items": list(
                self.review_items
            ),
        }
