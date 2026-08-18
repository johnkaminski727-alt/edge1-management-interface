"""Tests for Edge1 Operator turn-state store (T0b bounded spike)."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from server.edge1_operator_turn_state import (
    StaleEpochError,
    TurnStateStore,
    UnauthorizedOwnerError,
    UnknownTurnError,
)


class TestTurnStateStore(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="edge1-turn-state-test-"))
        self.audit_events = []
        self.store = TurnStateStore(
            root=str(self.tmp),
            audit_writer=lambda root, event: self.audit_events.append(event),
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unknown_task_conversation_status(self):
        with self.assertRaises(UnknownTurnError):
            self.store.status("task-x", "conv-x")

    def test_unknown_task_conversation_handoff(self):
        with self.assertRaises(UnknownTurnError):
            self.store.handoff(
                task_id="task-x",
                conversation_id="conv-x",
                requesting_agent="fen",
                to_agent="gus",
                expected_epoch=0,
                idempotency_key="k1",
            )

    def test_successful_handoff_and_status_readback(self):
        self.store.seed("task-1", "conv-1", owner_agent="fen")
        result = self.store.handoff(
            task_id="task-1",
            conversation_id="conv-1",
            requesting_agent="fen",
            to_agent="gus",
            expected_epoch=0,
            idempotency_key="k1",
        )
        self.assertEqual(result["owner_agent"], "gus")
        self.assertEqual(result["previous_owner"], "fen")
        self.assertEqual(result["turn_epoch"], 1)
        self.assertEqual(result["state"], "HANDED_OFF")

        status = self.store.status("task-1", "conv-1")
        self.assertEqual(status["owner_agent"], "gus")
        self.assertEqual(status["turn_epoch"], 1)

        self.assertEqual(len(self.audit_events), 1)
        self.assertEqual(self.audit_events[0]["event"], "turn.handed_off")
        self.assertEqual(self.audit_events[0]["from_agent"], "fen")
        self.assertEqual(self.audit_events[0]["to_agent"], "gus")

    def test_stale_epoch_rejected(self):
        self.store.seed("task-2", "conv-1", owner_agent="fen")
        self.store.handoff(
            task_id="task-2",
            conversation_id="conv-1",
            requesting_agent="fen",
            to_agent="gus",
            expected_epoch=0,
            idempotency_key="k1",
        )
        with self.assertRaises(StaleEpochError):
            self.store.handoff(
                task_id="task-2",
                conversation_id="conv-1",
                requesting_agent="gus",
                to_agent="fen",
                expected_epoch=0,
                idempotency_key="k2",
            )
        status = self.store.status("task-2", "conv-1")
        self.assertEqual(status["turn_epoch"], 1)
        self.assertEqual(status["owner_agent"], "gus")

    def test_duplicate_idempotent_replay_is_safe(self):
        self.store.seed("task-3", "conv-1", owner_agent="fen")
        first = self.store.handoff(
            task_id="task-3",
            conversation_id="conv-1",
            requesting_agent="fen",
            to_agent="gus",
            expected_epoch=0,
            idempotency_key="same-key",
        )
        second = self.store.handoff(
            task_id="task-3",
            conversation_id="conv-1",
            requesting_agent="fen",
            to_agent="gus",
            expected_epoch=0,
            idempotency_key="same-key",
        )
        self.assertEqual(first, second)
        self.assertEqual(len(self.audit_events), 1)

    def test_unauthorized_owner_rejected(self):
        self.store.seed("task-4", "conv-1", owner_agent="fen")
        with self.assertRaises(UnauthorizedOwnerError):
            self.store.handoff(
                task_id="task-4",
                conversation_id="conv-1",
                requesting_agent="gus",
                to_agent="fen",
                expected_epoch=0,
                idempotency_key="k1",
            )
        status = self.store.status("task-4", "conv-1")
        self.assertEqual(status["owner_agent"], "fen")
        self.assertEqual(status["turn_epoch"], 0)

    def test_restart_persistence(self):
        self.store.seed("task-5", "conv-1", owner_agent="fen")
        self.store.handoff(
            task_id="task-5",
            conversation_id="conv-1",
            requesting_agent="fen",
            to_agent="gus",
            expected_epoch=0,
            idempotency_key="k1",
        )
        fresh_store = TurnStateStore(root=str(self.tmp), audit_writer=None)
        status = fresh_store.status("task-5", "conv-1")
        self.assertEqual(status["owner_agent"], "gus")
        self.assertEqual(status["turn_epoch"], 1)


if __name__ == "__main__":
    unittest.main()
