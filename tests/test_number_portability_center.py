#!/usr/bin/env python3
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

from server.number_portability_center import PortabilityError, PortabilityStore


class NumberPortabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = PortabilityStore(Path(self.tmp.name) / "ports.sqlite3")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_inbound_case_requires_loa_and_csr_before_review(self) -> None:
        case = self.store.create_case(direction="inbound", customer_ref="cust-001", numbers=["3065551234"], losing_carrier="Carrier A", gaining_carrier="WW.CX")
        ready = self.store.readiness(case["id"])
        self.assertFalse(ready["ready_for_internal_review"])
        self.assertEqual(ready["missing_documents"], ["csr", "loa"])
        self.store.transition(case["id"], "collecting_documents")
        self.store.add_document(case["id"], document_type="loa", reference="drive:loa-001")
        self.store.add_document(case["id"], document_type="csr", reference="drive:csr-001")
        self.assertTrue(self.store.readiness(case["id"])["ready_for_internal_review"])
        reviewed = self.store.transition(case["id"], "ready_for_review")
        self.assertEqual(reviewed["state"], "ready_for_review")

    def test_live_submission_states_are_hard_blocked(self) -> None:
        case = self.store.create_case(direction="outbound", customer_ref="cust-002", numbers=["3065552345"], losing_carrier="WW.CX", gaining_carrier="Carrier B")
        with self.assertRaises(PortabilityError):
            self.store.transition(case["id"], "submitted")
        with self.assertRaises(PortabilityError):
            self.store.transition(case["id"], "foc_received")
        with self.assertRaises(PortabilityError):
            self.store.transition(case["id"], "completed")

    def test_invalid_number_is_rejected(self) -> None:
        with self.assertRaises(PortabilityError):
            self.store.create_case(direction="inbound", customer_ref="cust", numbers=["123"])

    def test_duplicate_numbers_are_deduplicated(self) -> None:
        case = self.store.create_case(direction="inbound", customer_ref="cust-003", numbers=["1-306-555-3456", "3065553456"], losing_carrier="Carrier A")
        self.assertEqual(len(case["numbers"]), 1)

    def test_approval_does_not_mean_submission(self) -> None:
        case = self.store.create_case(direction="inbound", customer_ref="cust-004", numbers=["3065554567"], losing_carrier="Carrier A")
        self.store.transition(case["id"], "collecting_documents")
        self.store.add_document(case["id"], document_type="loa", reference="drive:loa-004")
        self.store.add_document(case["id"], document_type="csr", reference="drive:csr-004")
        self.store.transition(case["id"], "ready_for_review")
        self.store.transition(case["id"], "awaiting_approval")
        case = self.store.transition(case["id"], "approved_for_submission")
        self.assertFalse(case["submission_authorized"])
        self.assertFalse(case["cutover_authorized"])


if __name__ == "__main__":
    unittest.main()
