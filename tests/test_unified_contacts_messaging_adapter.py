import json
import tempfile
import unittest
from pathlib import Path

from tools.unified_contacts.adapters.messaging import (
    extract,
    normalize_domain,
    normalize_email,
)


class MessagingAdapterTests(unittest.TestCase):

    def test_normalization(self):
        self.assertEqual(
            normalize_email(" User@Example.COM "),
            "user@example.com",
        )

        self.assertEqual(
            normalize_domain(" Example.COM. "),
            "example.com",
        )

    def test_extract_preserves_legal_alias_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            identities = root / "identities.json"
            inventory = root / "inventory.json"

            identities.write_text(
                json.dumps({
                    "domains": {
                        "example.com": {
                            "legal_name": "Example Incorporated",
                            "operating_name": "Example",
                        },
                    },
                    "sender_profiles": {
                        "support": {
                            "address": "support@example.com",
                            "display_name": "Example Support",
                            "organization": "Example",
                            "address_class": "work_role",
                        },
                    },
                })
            )

            inventory.write_text(
                json.dumps({
                    "domains": {
                        "example.com": {
                            "configured_but_unverified_addresses": [
                                "sales@example.com",
                            ],
                        },
                    },
                })
            )

            manifest = extract(
                identities,
                inventory,
            )

            names = {
                item.canonical_name
                for item in manifest.entities
            }

            self.assertIn(
                "Example Incorporated",
                names,
            )

            self.assertIn(
                "Example",
                names,
            )

            self.assertEqual(
                len(manifest.aliases),
                1,
            )

            self.assertEqual(
                manifest.aliases[0].alias_name,
                "Example",
            )

            # The source-named "Example" organization remains separate.
            # The adapter does not silently merge it into the legal entity.
            self.assertEqual(
                len(names),
                2,
            )

    def test_provider_address_does_not_create_relationship(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            identities = root / "identities.json"
            inventory = root / "inventory.json"

            identities.write_text(
                json.dumps({
                    "domains": {},
                    "sender_profiles": {},
                })
            )

            inventory.write_text(
                json.dumps({
                    "domains": {
                        "example.com": {
                            "verified_round_trip_addresses": [
                                "probe@example.com",
                            ],
                        },
                    },
                })
            )

            manifest = extract(
                identities,
                inventory,
            )

            self.assertEqual(
                len(manifest.relationships),
                0,
            )

            self.assertEqual(
                len(manifest.contact_points),
                1,
            )

    def test_idempotent_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            identities = root / "identities.json"
            inventory = root / "inventory.json"

            identities.write_text(
                json.dumps({
                    "domains": {
                        "example.com": {
                            "legal_name": "Example Inc.",
                            "operating_name": "Example",
                        },
                    },
                    "sender_profiles": {},
                })
            )

            inventory.write_text(
                json.dumps({
                    "domains": {},
                })
            )

            first = extract(
                identities,
                inventory,
            ).as_dict()

            second = extract(
                identities,
                inventory,
            ).as_dict()

            self.assertEqual(
                first,
                second,
            )


class MessagingAdapterSemanticTests(unittest.TestCase):

    def test_repeated_entity_sources_are_attestations_not_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            identities = root / "identities.json"
            inventory = root / "inventory.json"

            identities.write_text(json.dumps({
                "domains": {
                    "one.example": {
                        "legal_name": "Example Inc.",
                        "operating_name": "Example",
                    },
                    "two.example": {
                        "legal_name": "Example Inc.",
                        "operating_name": "Example",
                    },
                },
                "sender_profiles": {},
            }))

            inventory.write_text(
                json.dumps({"domains": {}})
            )

            manifest = extract(
                identities,
                inventory,
            )

            conflicts = [
                item
                for item in manifest.review_items
                if item["type"]
                == "entity_identity_conflict"
            ]

            self.assertEqual(conflicts, [])

            example = [
                item
                for item in manifest.entities
                if item.canonical_name
                == "Example Inc."
            ]

            self.assertEqual(
                len(example),
                1,
            )

            evidence = [
                item
                for item in manifest.attestations
                if item.subject_key
                == "organization:example inc."
            ]

            self.assertGreaterEqual(
                len(evidence),
                2,
            )

    def test_personal_sender_creates_person_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            identities = root / "identities.json"
            inventory = root / "inventory.json"

            identities.write_text(json.dumps({
                "domains": {},
                "sender_profiles": {
                    "person": {
                        "address": "person@example.com",
                        "display_name": "Example Person",
                        "organization": "Example Org",
                        "address_class": "private_person",
                    },
                },
            }))

            inventory.write_text(
                json.dumps({"domains": {}})
            )

            manifest = extract(
                identities,
                inventory,
            )

            people = [
                item
                for item in manifest.entities
                if item.entity_type == "person"
            ]

            self.assertEqual(
                len(people),
                1,
            )

            self.assertEqual(
                people[0].canonical_name,
                "Example Person",
            )

            person_links = [
                item
                for item in manifest.relationships
                if item.source_entity_key
                == "person:example person"
            ]

            self.assertEqual(
                len(person_links),
                1,
            )

    def test_multiple_email_classifications_are_attestations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            identities = root / "identities.json"
            inventory = root / "inventory.json"

            identities.write_text(json.dumps({
                "domains": {},
                "sender_profiles": {
                    "support": {
                        "address": "support@example.com",
                        "display_name": "Support",
                        "organization": "Example Org",
                        "address_class": "work_role",
                    },
                },
            }))

            inventory.write_text(json.dumps({
                "domains": {
                    "example.com": {
                        "verified_round_trip_addresses": [
                            "support@example.com",
                        ],
                    },
                },
            }))

            manifest = extract(
                identities,
                inventory,
            )

            points = [
                item
                for item in manifest.contact_points
                if item.normalized_value
                == "support@example.com"
            ]

            self.assertEqual(
                len(points),
                1,
            )

            evidence = [
                item
                for item in manifest.attestations
                if item.subject_key
                == "email:support@example.com"
            ]

            self.assertEqual(
                len(evidence),
                2,
            )

            conflicts = [
                item
                for item in manifest.review_items
                if item["type"]
                == "contact_point_identity_conflict"
            ]

            self.assertEqual(
                conflicts,
                [],
            )


if __name__ == "__main__":
    unittest.main()
