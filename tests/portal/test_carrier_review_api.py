#!/usr/bin/env python3

import json
import tempfile
import unittest
from pathlib import Path

from server.portal.carrier_operational import PortalIdentity
from server.portal.carrier_review import REVIEW_READ_SCOPE, REVIEW_WRITE_SCOPE, ReviewValidationError
from server.portal.carrier_review_api import (
    ReviewAuthorizationError,
    create_review_event,
    review_queue_response,
)


class CarrierReviewApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.tickets = self.root / "tickets.jsonl"
        self.changes = self.root / "changes.jsonl"
        self.reviews = self.root / "reviews.jsonl"
        self.tickets.write_text(json.dumps({
            "ticket_id": "TKT-AAAAAAAAAAAA",
            "carrier_id": "carrier-alpha",
            "summary": "Test ticket",
            "created_at": "2026-07-21T00:00:00+00:00",
        }) + "\n", encoding="utf-8")
        self.changes.write_text(json.dumps({
            "change_request_id": "CRQ-BBBBBBBBBBBB",
            "carrier_id": "carrier-alpha",
            "summary": "Test change",
            "execution_authorized": False,
            "created_at": "2026-07-21T00:01:00+00:00",
        }) + "\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def identity(self, scopes, carrier_id=None):
        return PortalIdentity("internal-reviewer", carrier_id, frozenset(scopes))

    def test_internal_reader_can_read_queue(self):
        payload = review_queue_response(
            self.identity([REVIEW_READ_SCOPE]),
            self.tickets,
            self.changes,
            self.reviews,
        )
        self.assertEqual(payload["count"], 2)
        self.assertFalse(payload["execution_authorized"])

    def test_carrier_identity_is_rejected_even_with_internal_scope(self):
        with self.assertRaisesRegex(ReviewAuthorizationError, "carrier identities"):
            review_queue_response(
                self.identity([REVIEW_READ_SCOPE], carrier_id="carrier-alpha"),
                self.tickets,
                self.changes,
                self.reviews,
            )

    def test_reader_without_scope_is_rejected(self):
        with self.assertRaisesRegex(ReviewAuthorizationError, "scope denied"):
            review_queue_response(
                self.identity([]),
                self.tickets,
                self.changes,
                self.reviews,
            )

    def test_internal_writer_can_append_review_event(self):
        event = create_review_event(
            self.identity([REVIEW_WRITE_SCOPE]),
            self.reviews,
            self.tickets,
            self.changes,
            {
                "resource_type": "ticket",
                "resource_id": "TKT-AAAAAAAAAAAA",
                "action": "acknowledge",
                "note": "Received",
            },
        )
        self.assertEqual(event["status"], "acknowledged")
        self.assertFalse(event["approval_granted"])
        self.assertFalse(event["execution_authorized"])
        self.assertTrue(self.reviews.exists())

    def test_writer_without_scope_is_rejected(self):
        with self.assertRaisesRegex(ReviewAuthorizationError, "scope denied"):
            create_review_event(
                self.identity([REVIEW_READ_SCOPE]),
                self.reviews,
                self.tickets,
                self.changes,
                {
                    "resource_type": "ticket",
                    "resource_id": "TKT-AAAAAAAAAAAA",
                    "action": "acknowledge",
                },
            )

    def test_approval_action_remains_rejected(self):
        with self.assertRaises(ReviewValidationError):
            create_review_event(
                self.identity([REVIEW_WRITE_SCOPE]),
                self.reviews,
                self.tickets,
                self.changes,
                {
                    "resource_type": "change_request",
                    "resource_id": "CRQ-BBBBBBBBBBBB",
                    "action": "approve",
                },
            )


if __name__ == "__main__":
    unittest.main()
