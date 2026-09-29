import unittest

from server.edge1_security_auth_core import AuthorizationError
from server.unified_contacts_review_http import (
    ACTION_MAP,
    CONTACTS_REVIEW_SCOPE,
    ContactsReviewAdapter,
)


class Context:
    subject = "john"
    scopes = {CONTACTS_REVIEW_SCOPE}


class Gateway:
    def __init__(self, scopes=None):
        self.scopes = (
            {CONTACTS_REVIEW_SCOPE}
            if scopes is None
            else set(scopes)
        )

    def authenticate_session(self, token, request_id):
        if token != "session-token":
            raise RuntimeError("unexpected session")

        context = Context()
        context.scopes = self.scopes
        return context


class Result:
    action_id = "contacts.correlation.accept"
    status = "succeeded"
    message = "ok"
    event_id = "event-1"


class Operations:
    def __init__(self):
        self.calls = []

    def run(self, action, actor, parameters=None):
        self.calls.append(
            (action, actor, parameters)
        )

        result = Result()
        result.action_id = action
        return result


class ContactsReviewAdapterTests(unittest.TestCase):
    def setUp(self):
        self.operations = Operations()
        self.adapter = ContactsReviewAdapter(
            Gateway(),
            self.operations,
        )

    def test_action_map_exact(self):
        self.assertEqual(
            ACTION_MAP,
            {
                "accept":
                    "contacts.correlation.accept",
                "reject":
                    "contacts.correlation.reject",
                "promote":
                    "contacts.correlation.promote",
            },
        )

    def test_parse_accept_path(self):
        self.assertEqual(
            self.adapter.parse_path(
                "/edge1-ops/api/v1/contacts/"
                "correlations/12/accept"
            ),
            (12, "accept"),
        )

    def test_parse_reject_path(self):
        self.assertEqual(
            self.adapter.parse_path(
                "/edge1-ops/api/v1/contacts/"
                "correlations/12/reject"
            ),
            (12, "reject"),
        )

    def test_parse_promote_path(self):
        self.assertEqual(
            self.adapter.parse_path(
                "/edge1-ops/api/v1/contacts/"
                "correlations/12/promote"
            ),
            (12, "promote"),
        )

    def test_rejects_boolean_like_or_zero_candidate(self):
        for value in ("0", "00", "-1", "true"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.adapter.parse_path(
                        "/edge1-ops/api/v1/contacts/"
                        f"correlations/{value}/accept"
                    )

    def test_accept_payload_must_be_empty(self):
        self.assertEqual(
            self.adapter.parse_payload(
                "accept",
                b"{}",
            ),
            {},
        )

        with self.assertRaises(ValueError):
            self.adapter.parse_payload(
                "accept",
                b'{"provenance_id":1}',
            )

    def test_promote_requires_provenance(self):
        with self.assertRaises(ValueError):
            self.adapter.parse_payload(
                "promote",
                b"{}",
            )

        self.assertEqual(
            self.adapter.parse_payload(
                "promote",
                b'{"provenance_id":7}',
            ),
            {"provenance_id": 7},
        )

    def test_promote_rejects_boolean_provenance(self):
        with self.assertRaises(ValueError):
            self.adapter.parse_payload(
                "promote",
                b'{"provenance_id":true}',
            )

    def test_requires_csrf(self):
        with self.assertRaises(AuthorizationError):
            self.adapter.review(
                session_token="session-token",
                request_id="request-1",
                csrf_validated=False,
                candidate_id=3,
                operation="accept",
                parameters={},
            )

    def test_requires_review_scope(self):
        adapter = ContactsReviewAdapter(
            Gateway(scopes=set()),
            self.operations,
        )

        with self.assertRaises(AuthorizationError):
            adapter.review(
                session_token="session-token",
                request_id="request-2",
                csrf_validated=True,
                candidate_id=3,
                operation="accept",
                parameters={},
            )

    def test_accept_calls_typed_operation(self):
        result = self.adapter.review(
            session_token="session-token",
            request_id="request-3",
            csrf_validated=True,
            candidate_id=8,
            operation="accept",
            parameters={},
        )

        self.assertEqual(result.status_code, 200)

        self.assertEqual(
            self.operations.calls,
            [
                (
                    "contacts.correlation.accept",
                    "john",
                    {"candidate_id": 8},
                )
            ],
        )

    def test_promote_parameters_remain_server_action_parameters(self):
        self.adapter.review(
            session_token="session-token",
            request_id="request-4",
            csrf_validated=True,
            candidate_id=9,
            operation="promote",
            parameters={
                "provenance_id": 22,
                "evidence_role": "supporting",
            },
        )

        self.assertEqual(
            self.operations.calls[0][2],
            {
                "candidate_id": 9,
                "provenance_id": 22,
                "evidence_role": "supporting",
            },
        )


if __name__ == "__main__":
    unittest.main()
