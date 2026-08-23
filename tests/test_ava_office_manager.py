#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from server.ava_office_manager import OfficeManagerError, OfficeManagerStore, load_policy


class AvaOfficeManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "ava-office-manager.sqlite3"
        self.store = OfficeManagerStore(self.db)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_work_item_lifecycle_and_cross_channel_artifacts(self) -> None:
        item = self.store.create_work_item(
            title="Arrange dentist appointment",
            desired_outcome="Book an afternoon appointment next week.",
            source_channel="chat",
            source_ref="conversation:abc123",
        )
        self.assertEqual(item["state"], "new")
        artifact = self.store.link_artifact(
            item["id"],
            kind="call",
            ref="call:opaque-001",
            label="Scheduling call",
        )
        self.assertEqual(artifact["work_item_id"], item["id"])
        item = self.store.transition_work_item(item["id"], "working")
        item = self.store.transition_work_item(item["id"], "waiting_external")
        self.assertEqual(item["state"], "waiting_external")
        self.assertEqual(len(item["artifacts"]), 1)
        self.assertTrue(self.store.verify_audit_chain())

    def test_routine_action_is_plannable_but_not_executable_by_default(self) -> None:
        decision = self.store.evaluate_action("calendar.event.create", {"slot_id": "slot-001"})
        self.assertEqual(decision.authorization, "allowed")
        self.assertEqual(decision.authority, "routine")
        self.assertFalse(decision.executable)
        self.assertIn("execution gate is disabled", decision.reason)

    def test_prepare_action_never_implies_external_execution(self) -> None:
        decision = self.store.evaluate_action("communication.draft", {"recipient_ref": "contact-001"})
        self.assertEqual(decision.authorization, "allowed")
        self.assertEqual(decision.authority, "prepare")
        self.assertFalse(decision.executable)

    def test_confirmation_and_hard_block_boundaries(self) -> None:
        confirm = self.store.propose_action(
            capability="travel.book",
            summary="Book the selected itinerary",
            parameters={"itinerary_ref": "option-001"},
        )
        self.assertEqual(confirm["status"], "awaiting_confirmation")
        self.assertFalse(confirm["executable"])

        blocked = self.store.propose_action(
            capability="contract.sign",
            summary="Sign a vendor contract",
            parameters={"document_ref": "doc-001"},
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertFalse(blocked["executable"])

    def test_owner_approval_does_not_bypass_disabled_execution_gate(self) -> None:
        proposal = self.store.propose_action(
            capability="telephony.originate",
            summary="Call an approved contact for scheduling",
            parameters={"contact_ref": "contact-001"},
        )
        approved = self.store.approve_action(proposal["id"], actor="john")
        self.assertEqual(approved["status"], "approved")
        self.assertFalse(approved["executable"])
        self.assertIn("disabled", approved["reason"])

    def test_standing_instruction_can_deny_a_normally_routine_action(self) -> None:
        self.store.add_standing_instruction(
            domain="calendar.event.create",
            statement="Do not create calendar events while testing.",
            effect="deny",
        )
        decision = self.store.evaluate_action("calendar.event.create", {"slot_id": "slot-002"})
        self.assertEqual(decision.authorization, "blocked")
        self.assertFalse(decision.executable)

    def test_sensitive_action_parameters_are_rejected(self) -> None:
        with self.assertRaises(OfficeManagerError):
            self.store.propose_action(
                capability="calendar.event.create",
                summary="Bad proposal",
                parameters={"api_key": "do-not-store-this"},
            )

    def test_unknown_capability_fails_closed(self) -> None:
        decision = self.store.evaluate_action("vendor.unspecified.magic", {})
        self.assertEqual(decision.authority, "restricted")
        self.assertEqual(decision.authorization, "blocked")
        self.assertFalse(decision.executable)
        self.assertIn("no commissioned control-plane rule", decision.reason)

    def test_invalid_state_transition_is_rejected(self) -> None:
        item = self.store.create_work_item(
            title="Return equipment",
            desired_outcome="Obtain return instructions and verify credit.",
            source_channel="email",
        )
        with self.assertRaises(OfficeManagerError):
            self.store.transition_work_item(item["id"], "completed")

    def test_repository_policy_matches_module_contract(self) -> None:
        policy_path = Path(__file__).parents[1] / "config" / "ava-office-manager-policy.json"
        policy = load_policy(policy_path)
        self.assertFalse(policy["execution_enabled"])
        self.assertEqual(policy["autonomy_level"], "routine")
        self.assertIn("contract.sign", policy["blocked_prefixes"])
        self.assertIn("telephony.originate", policy["always_confirm_prefixes"])

    def test_policy_with_execution_enabled_still_preserves_hard_gates(self) -> None:
        policy_path = Path(__file__).parents[1] / "config" / "ava-office-manager-policy.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        policy["execution_enabled"] = True
        enabled = OfficeManagerStore(Path(self.tmp.name) / "enabled.sqlite3", policy=policy)
        routine = enabled.evaluate_action("calendar.event.create", {"slot_id": "slot-003"})
        self.assertTrue(routine.executable)
        blocked = enabled.evaluate_action("financial.transfer", {"amount_minor": 1})
        self.assertEqual(blocked.authorization, "blocked")
        self.assertFalse(blocked.executable)
        unknown = enabled.evaluate_action("provider.uncommissioned.action", {})
        self.assertEqual(unknown.authorization, "blocked")
        self.assertFalse(unknown.executable)


if __name__ == "__main__":
    unittest.main()
