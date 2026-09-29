import unittest
from unittest.mock import Mock

from server.edge1_security_auth_http_types import HttpRequest
from server.unified_contacts_review_http import (
    CONTACTS_REVIEW_SCOPE,
)


class ContactsReviewHttpIntegrationContractTests(unittest.TestCase):
    def test_review_scope_is_exact(self):
        self.assertEqual(
            CONTACTS_REVIEW_SCOPE,
            "edge1.contacts.relationships.review",
        )

    def test_browser_route_namespace_is_private_ops(self):
        from server.unified_contacts_review_http import ContactsReviewAdapter

        self.assertEqual(
            ContactsReviewAdapter.parse_path(
                "/edge1-ops/api/v1/contacts/correlations/17/accept"
            ),
            (17, "accept"),
        )

    def test_unknown_contacts_operation_is_not_a_route(self):
        from server.unified_contacts_review_http import ContactsReviewAdapter

        self.assertIsNone(
            ContactsReviewAdapter.parse_path(
                "/edge1-ops/api/v1/contacts/correlations/17/merge"
            )
        )


if __name__ == "__main__":
    unittest.main()


class ExecutableContactsRouteContractTests(unittest.TestCase):
    def test_contacts_method_uses_real_session_and_csrf_helpers(self):
        import inspect

        from server.edge1_security_auth_http import (
            Edge1SecurityAuthHttpAdapter,
        )

        source = inspect.getsource(
            Edge1SecurityAuthHttpAdapter._contacts_review_action
        )

        self.assertIn(
            "self._session_token(request)",
            source,
        )
        self.assertIn(
            "self._request_id()",
            source,
        )
        self.assertIn(
            "context.session_identifier_hash",
            source,
        )
        self.assertIn(
            "self._require_csrf(",
            source,
        )
        self.assertIn(
            "csrf_validated=True",
            source,
        )

        self.assertNotIn(
            "_session_cookie",
            source,
        )
        self.assertNotIn(
            "_request_id(request)",
            source,
        )

    def test_contacts_method_helper_signatures_match_calls(self):
        import inspect

        from server.edge1_security_auth_http import (
            Edge1SecurityAuthHttpAdapter,
        )

        session_signature = inspect.signature(
            Edge1SecurityAuthHttpAdapter._session_token
        )

        csrf_signature = inspect.signature(
            Edge1SecurityAuthHttpAdapter._require_csrf
        )

        request_id_signature = inspect.signature(
            Edge1SecurityAuthHttpAdapter._request_id
        )

        self.assertEqual(
            list(session_signature.parameters),
            ["self", "request"],
        )

        self.assertEqual(
            list(csrf_signature.parameters),
            ["self", "request", "session_hash"],
        )

        self.assertEqual(
            list(request_id_signature.parameters),
            ["self"],
        )
