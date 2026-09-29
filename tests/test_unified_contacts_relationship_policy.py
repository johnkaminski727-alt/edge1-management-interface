import unittest

from tools.unified_contacts.relationship_policy import (
    RELATIONSHIP_DEFINITIONS,
    can_promote_candidate,
    promotion_confidence,
    relationship_definition,
    validate_relationship,
)


class RelationshipPolicyTests(unittest.TestCase):

    def test_vocabulary_is_explicit(self):
        expected = {
            "works_for",
            "operates_as",
            "vendor_of",
            "member_of",
            "associated_project",
            "communicated_with",
            "same_document",
            "shared_address",
            "shared_contact_point",
            "associated_with",
            "possible_match",
        }

        self.assertEqual(
            set(RELATIONSHIP_DEFINITIONS),
            expected,
        )

    def test_directionality_is_explicit(self):
        self.assertEqual(
            relationship_definition(
                "works_for"
            ).directionality,
            "directed",
        )

        self.assertEqual(
            relationship_definition(
                "shared_contact_point"
            ).directionality,
            "undirected",
        )

    def test_unknown_type_rejected(self):
        with self.assertRaises(ValueError):
            relationship_definition(
                "looks_related"
            )

    def test_directionality_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            validate_relationship(
                "works_for",
                "document_sourced",
                "undirected",
            )

    def test_possible_match_is_candidate_only(self):
        definition = relationship_definition(
            "possible_match"
        )

        self.assertTrue(
            definition.candidate_only
        )

        self.assertFalse(
            definition.durable
        )

        with self.assertRaises(ValueError):
            validate_relationship(
                "possible_match",
                "unverified",
                "undirected",
                candidate=False,
            )

        self.assertTrue(
            validate_relationship(
                "possible_match",
                "possible",
                "undirected",
                candidate=True,
            )
        )

    def test_same_document_is_context_only(self):
        definition = relationship_definition(
            "same_document"
        )

        self.assertEqual(
            definition.category,
            "context",
        )

        self.assertIn(
            "does not imply",
            definition.description,
        )

    def test_shared_contact_does_not_mean_identity(self):
        definition = relationship_definition(
            "shared_contact_point"
        )

        self.assertEqual(
            definition.category,
            "context",
        )

        self.assertIn(
            "does not imply identity",
            definition.description,
        )

    def test_candidate_requires_acceptance_to_promote(self):
        self.assertFalse(
            can_promote_candidate(
                "vendor_of",
                "probable",
                "pending",
            )
        )

        self.assertTrue(
            can_promote_candidate(
                "vendor_of",
                "probable",
                "accepted",
            )
        )

    def test_possible_match_never_promotes_directly(self):
        self.assertFalse(
            can_promote_candidate(
                "possible_match",
                "probable",
                "accepted",
            )
        )

    def test_promotion_confidence_uses_provenance(self):
        self.assertEqual(
            promotion_confidence(
                "possible",
                "verified",
            ),
            "confirmed",
        )

        self.assertEqual(
            promotion_confidence(
                "possible",
                "document_sourced",
            ),
            "document_sourced",
        )

        self.assertEqual(
            promotion_confidence(
                "probable",
                "missing_source",
            ),
            "probable",
        )

        self.assertEqual(
            promotion_confidence(
                "possible",
                "unverified",
            ),
            "unverified",
        )



if __name__ == "__main__":
    unittest.main()
