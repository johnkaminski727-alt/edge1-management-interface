"""Tests that agent.turn.status / agent.turn.handoff are correctly wired
through the existing MCPAdapter.call_tool pattern (T0b)."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from server.edge1_operator_mcp_adapter import MCPAdapter
from server.edge1_operator_turn_state import TurnStateStore


class TestTurnToolsThroughAdapter(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="edge1-turn-tools-test-"))
        self.store = TurnStateStore(root=str(self.tmp), audit_writer=None)
        self.adapter = MCPAdapter(runtime=None, turn_store=self.store)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_turn_tools_are_listed(self):
        tools = self.adapter.list_tools()
        self.assertIn("agent.turn.status", tools)
        self.assertIn("agent.turn.handoff", tools)

    def test_existing_zero_arg_tools_still_reject_parameters(self):
        # unrelated to turn state, but proves the surgical change didn't
        # loosen the contract for the other 16 tools
        result = self.adapter.call_tool("edge1.health", task_id="x")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.payload["message"], "parameters_not_accepted")

    def test_status_through_call_tool_unknown(self):
        result = self.adapter.call_tool(
            "agent.turn.status", task_id="t1", conversation_id="c1"
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.payload["message"], "unknown_task_conversation")

    def test_handoff_through_call_tool_full_cycle(self):
        self.store.seed("t2", "c1", owner_agent="fen")

        handoff_result = self.adapter.call_tool(
            "agent.turn.handoff",
            task_id="t2",
            conversation_id="c1",
            requesting_agent="fen",
            to_agent="gus",
            expected_epoch=0,
            idempotency_key="k1",
        )
        self.assertEqual(handoff_result.status, "ok")
        self.assertEqual(handoff_result.payload["owner_agent"], "gus")

        status_result = self.adapter.call_tool(
            "agent.turn.status", task_id="t2", conversation_id="c1"
        )
        self.assertEqual(status_result.status, "ok")
        self.assertEqual(status_result.payload["owner_agent"], "gus")

    def test_unauthorized_and_stale_epoch_map_to_error_results(self):
        self.store.seed("t3", "c1", owner_agent="fen")

        unauthorized = self.adapter.call_tool(
            "agent.turn.handoff",
            task_id="t3",
            conversation_id="c1",
            requesting_agent="gus",
            to_agent="fen",
            expected_epoch=0,
            idempotency_key="k1",
        )
        self.assertEqual(unauthorized.status, "error")
        self.assertEqual(unauthorized.payload["message"], "unauthorized_owner")

        stale = self.adapter.call_tool(
            "agent.turn.handoff",
            task_id="t3",
            conversation_id="c1",
            requesting_agent="fen",
            to_agent="gus",
            expected_epoch=99,
            idempotency_key="k2",
        )
        self.assertEqual(stale.status, "error")
        self.assertEqual(stale.payload["message"], "stale_epoch")

    def test_idempotency_conflict_maps_to_error_result(self):
        self.store.seed("t4", "c1", owner_agent="fen")
        first = self.adapter.call_tool(
            "agent.turn.handoff",
            task_id="t4",
            conversation_id="c1",
            requesting_agent="fen",
            to_agent="gus",
            expected_epoch=0,
            idempotency_key="dup-key",
        )
        self.assertEqual(first.status, "ok")

        conflict = self.adapter.call_tool(
            "agent.turn.handoff",
            task_id="t4",
            conversation_id="c1",
            requesting_agent="gus",
            to_agent="edge1-ai",
            expected_epoch=1,
            idempotency_key="dup-key",
        )
        self.assertEqual(conflict.status, "error")
        self.assertEqual(conflict.payload["message"], "idempotency_conflict")

    def test_turn_store_unavailable_is_a_clean_error_not_a_crash(self):
        adapter_without_store = MCPAdapter(runtime=None, turn_store=None)
        result = adapter_without_store.call_tool(
            "agent.turn.status", task_id="t1", conversation_id="c1"
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.payload["message"], "turn_store_unavailable")


if __name__ == "__main__":
    unittest.main()
