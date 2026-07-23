#!/usr/bin/env python3

import json
import tempfile
import unittest
from pathlib import Path

from server.portal.carrier_review import (
    ReviewValidationError,
    append_review_event,
    build_review_queue,
)


class CarrierReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.tickets = self.root / "tickets.jsonl"
        self.changes = self.root / "changes.jsonl"
        self.reviews = self.root / "reviews.jsonl"

        self.ticket = {
            "ticket_id": "TKT-ABCDEF123456",
            "carrier_id": "carrier-alpha",
            "client_id": "carrier-workflow",
            "status": "open",
            "summary": "Ticket",
            "created_at": "2026-07-21T00:00:00+00:00",
        }
        self.change = {
            "change_request_id": "CRQ-ABCDEF123456",
            "carrier_id": "carrier-alpha",
            "client_id": "carrier-workflow",
            "status": "requested",
            "summary": "Change",
            "execution_authorized": False,
            "created_at": "2026-07-21T00:01:00+00:00",
        }
        self.tickets.write_text(json.dumps(self.ticket) + "\n", encoding="utf-8")
        self.changes.write_text(json.dumps(self.change) + "\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_queue_includes_unreviewed_records_and_never_authorizes_execution(self):
        queue = build_review_queue(self.tickets, self.changes, self.reviews)
        self.assertEqual(queue["count"], 2)
        self.assertFalse(queue["execution_authorized"])
        self.assertTrue(all(not item["execution_authorized"] for item in queue["items"]))
        self.assertTrue(all(item["review_status"] == "unreviewed" for item in queue["items"]))

    def test_append_review_event_updates_queue_overlay(self):
        event = append_review_event(
            self.reviews,
            self.tickets,
            self.changes,
            "internal-reviewer",
            {
                "resource_type": "ticket",
                "resource_id": "TKT-ABCDEF123456",
                "action": "begin_review",
                "note": "Investigating.",
            },
        )
        self.assertEqual(event["status"], "under_review")
        self.assertFalse(event["approval_granted"])
        self.assertFalse(event["execution_authorized"])

        queue = build_review_queue(self.tickets, self.changes, self.reviews)
        ticket = next(item for item in queue["items"] if item["resource_type"] == "ticket")
        self.assertEqual(ticket["review_status"], "under_review")
        self.assertEqual(ticket["reviewed_by"], "internal-reviewer")

    def test_change_rejection_is_non_executing(self):
        event = append_review_event(
            self.reviews,
            self.tickets,
            self.changes,
            "internal-reviewer",
            {
                "resource_type": "change_request",
                "resource_id": "CRQ-ABCDEF123456",
                "action": "reject_change",
            },
        )
        self.assertEqual(event["status"], "rejected")
        self.assertFalse(event["approval_granted"])
        self.assertFalse(event["execution_authorized"])

    def test_disallows_approval_or_execution_actions(self):
        for action in ("approve", "authorize", "execute", "schedule"):
            with self.subTest(action=action):
                with self.assertRaises(ReviewValidationError):
                    append_review_event(
                        self.reviews,
                        self.tickets,
                        self.changes,
                        "internal-reviewer",
                        {
                            "resource_type": "change_request",
                            "resource_id": "CRQ-ABCDEF123456",
                            "action": action,
                        },
                    )

    def test_rejects_cross_type_actions(self):
        with self.assertRaises(ReviewValidationError):
            append_review_event(
                self.reviews,
                self.tickets,
                self.changes,
                "internal-reviewer",
                {
                    "resource_type": "ticket",
                    "resource_id": "TKT-ABCDEF123456",
                    "action": "reject_change",
                },
            )

    def test_rejects_unknown_resource(self):
        with self.assertRaisesRegex(ReviewValidationError, "resource not found"):
            append_review_event(
                self.reviews,
                self.tickets,
                self.changes,
                "internal-reviewer",
                {
                    "resource_type": "ticket",
                    "resource_id": "TKT-000000000000",
                    "action": "acknowledge",
                },
            )

    def test_latest_event_controls_review_overlay(self):
        for action in ("acknowledge", "request_information"):
            append_review_event(
                self.reviews,
                self.tickets,
                self.changes,
                "internal-reviewer",
                {
                    "resource_type": "ticket",
                    "resource_id": "TKT-ABCDEF123456",
                    "action": action,
                },
            )
        queue = build_review_queue(self.tickets, self.changes, self.reviews)
        ticket = next(item for item in queue["items"] if item["resource_type"] == "ticket")
        self.assertEqual(ticket["review_status"], "information_requested")


if __name__ == "__main__":
    unittest.main()
