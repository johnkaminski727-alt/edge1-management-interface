"""Tests for Edge1 Operator turn-state store (T0b, SQLite-backed atomic version)."""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
import threading
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

    def test_forced_mid_transaction_rollback_leaves_no_partial_rows(self):
        self.store.seed("task-6", "conv-1", owner_agent="fen")

        class InjectedFailure(Exception):
            pass

        def fail_after_state_update(checkpoint):
            if checkpoint == "after_state_update":
                raise InjectedFailure("forced rollback for test")

        faulty_store = TurnStateStore(
            root=str(self.tmp),
            audit_writer=None,
            _fault_injector=fail_after_state_update,
        )

        with self.assertRaises(InjectedFailure):
            faulty_store.handoff(
                task_id="task-6",
                conversation_id="conv-1",
                requesting_agent="fen",
                to_agent="gus",
                expected_epoch=0,
                idempotency_key="k1",
            )

        # State must be completely unchanged -- the UPDATE that ran before
        # the injected failure must have been rolled back along with
        # everything else in the same transaction.
        status = self.store.status("task-6", "conv-1")
        self.assertEqual(status["owner_agent"], "fen")
        self.assertEqual(status["turn_epoch"], 0)

        conn = sqlite3.connect(str(self.store.db_path))
        try:
            audit_count = conn.execute(
                "SELECT COUNT(*) FROM turn_audit WHERE task_id = ?", ("task-6",)
            ).fetchone()[0]
            outbox_count = conn.execute(
                "SELECT COUNT(*) FROM turn_outbox WHERE task_id = ?", ("task-6",)
            ).fetchone()[0]
            idem_count = conn.execute(
                "SELECT COUNT(*) FROM turn_idempotency WHERE task_id = ?", ("task-6",)
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(audit_count, 0)
        self.assertEqual(outbox_count, 0)
        self.assertEqual(idem_count, 0)

    def test_two_writer_same_epoch_race_only_one_succeeds(self):
        self.store.seed("task-7", "conv-1", owner_agent="fen")

        results = {}
        errors = {}

        def attempt(name, to_agent, key):
            try:
                results[name] = self.store.handoff(
                    task_id="task-7",
                    conversation_id="conv-1",
                    requesting_agent="fen",
                    to_agent=to_agent,
                    expected_epoch=0,
                    idempotency_key=key,
                )
            except (StaleEpochError, UnauthorizedOwnerError) as exc:
                # Both threads race as the same original owner ("fen"). The
                # loser's rejection reason depends on exact timing: if it
                # re-reads after the winner's commit, ownership has already
                # moved on, so UnauthorizedOwnerError is the natural (and
                # equally valid) outcome, not necessarily StaleEpochError.
                # What matters is that exactly one writer succeeds and the
                # other is safely rejected without corrupting state -- not
                # which specific exception subtype it gets.
                errors[name] = exc

        t1 = threading.Thread(target=attempt, args=("t1", "gus", "race-key-1"))
        t2 = threading.Thread(target=attempt, args=("t2", "edge1-ai", "race-key-2"))
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        self.assertEqual(len(results), 1, f"expected exactly one winner, got {results} / {errors}")
        self.assertEqual(len(errors), 1, f"expected exactly one stale-epoch loser, got {results} / {errors}")

        final = self.store.status("task-7", "conv-1")
        self.assertEqual(final["turn_epoch"], 1)
        self.assertIn(final["owner_agent"], ("gus", "edge1-ai"))


if __name__ == "__main__":
    unittest.main()
