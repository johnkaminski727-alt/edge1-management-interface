#!/usr/bin/env python3

import unittest

from server import phone_intelligence_gateway as gateway


class ConnectionsGatewayRouteTests(unittest.TestCase):

    def test_relationships_route(self):
        self.assertEqual(
            gateway.translate_api_path(
                "/api/contacts/relationships"
            ),
            "/v1/contacts/relationships",
        )

    def test_relationships_query_forwarding(self):
        translated = gateway.translate_api_path(
            "/api/contacts/relationships"
            "?entity_id=59"
            "&relationship_type=works_for"
            "&confidence=document_sourced"
            "&lifecycle_status=active"
            "&limit=25"
            "&offset=0"
        )

        self.assertIsNotNone(translated)

        self.assertTrue(
            translated.startswith(
                "/v1/contacts/relationships?"
            )
        )

        for fragment in (
            "entity_id=59",
            "relationship_type=works_for",
            "confidence=document_sourced",
            "lifecycle_status=active",
            "limit=25",
            "offset=0",
        ):
            self.assertIn(fragment, translated)

    def test_relationship_evidence_route(self):
        self.assertEqual(
            gateway.translate_api_path(
                "/api/contacts/relationship-evidence"
                "?relationship_id=1"
            ),
            (
                "/v1/contacts/relationship-evidence"
                "?relationship_id=1"
            ),
        )

    def test_correlations_route(self):
        translated = gateway.translate_api_path(
            "/api/contacts/correlations"
            "?review_status=pending"
            "&correlation_type=possible_match"
            "&entity_id=59"
            "&limit=100"
            "&offset=0"
        )

        self.assertIsNotNone(translated)

        self.assertTrue(
            translated.startswith(
                "/v1/contacts/correlations?"
            )
        )

    def test_unknown_relationship_query_rejected(self):
        self.assertIsNone(
            gateway.translate_api_path(
                "/api/contacts/relationships"
                "?mutate=true"
            )
        )

    def test_unknown_correlation_query_rejected(self):
        self.assertIsNone(
            gateway.translate_api_path(
                "/api/contacts/correlations"
                "?accept=true"
            )
        )

    def test_no_mutation_routes(self):
        for path in (
            "/api/contacts/correlations/accept",
            "/api/contacts/correlations/reject",
            "/api/contacts/correlations/promote",
            "/api/contacts/relationships/create",
            "/api/contacts/relationships/delete",
        ):
            self.assertIsNone(
                gateway.translate_api_path(path)
            )


if __name__ == "__main__":
    unittest.main()
