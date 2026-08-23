#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
from unittest import mock

from server import edge1_operations_api as operations_api
from server.edge1_operator_capabilities import CapabilityEvaluator, CapabilityConfigurationError
from server.edge1_operator_mcp_adapter import MCPAdapter
from server.edge1_operator_mcp_protocol import PUBLIC_EDGE1_TOOL_NAMES, TOOLS
from server.edge1_operator_runtime import Edge1OperatorRuntime
from server.edge1_operations_typed_actions import TypedActionValidationError, run_typed_handler

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "config/edge1-operator-capabilities.json").read_text(encoding="utf-8"))
ALLOWLIST = json.loads((ROOT / "config/edge1-operations-allowlist.json").read_text(encoding="utf-8"))
OPS_SERVICE = (ROOT / "deploy/edge1-operations-api.service").read_text(encoding="utf-8")


class FakeClient:
    def __init__(self):
        self.calls = []

    def health(self):
        return {"status": "ok"}

    def run_action(self, action, parameters=None):
        self.calls.append((action, parameters))
        return {"action": action, "status": "succeeded", "parameters": parameters}


class OperatorControlsV1Tests(unittest.TestCase):
    def test_every_public_tool_is_in_exactly_one_capability(self):
        assigned = []
        for policy in MANIFEST["capabilities"].values():
            assigned.extend(policy["tools"])
        self.assertEqual(set(assigned), set(PUBLIC_EDGE1_TOOL_NAMES))
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertNotIn("agent.turn.status", assigned)
        self.assertNotIn("agent.turn.handoff", assigned)

    def test_default_scopes_are_read_only_and_deny_reload(self):
        evaluator = CapabilityEvaluator(manifest=MANIFEST)
        self.assertTrue(evaluator.decision("edge1.telephony_status")["allowed"])
        decision = evaluator.decision("edge1.telephony_console_reload")
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "required_scope_missing")

    def test_scoped_reload_uses_one_fixed_operations_action(self):
        client = FakeClient()
        evaluator = CapabilityEvaluator(
            manifest=MANIFEST,
            scopes=frozenset({
                "edge1.status.read",
                "edge1.telephony.read",
                "edge1.messaging.read",
                "edge1.telephony.control.safe",
            }),
        )
        runtime = Edge1OperatorRuntime(client=client, capabilities=evaluator)
        result = runtime.telephony_console_reload(
            expected_pid=123,
            expected_source_sha256="a" * 64,
            expected_repo_head="b" * 40,
            idempotency_key="operator-control-0001",
        )
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(
            client.calls,
            [(
                "telephony.console.reload_safe",
                {
                    "expected_pid": 123,
                    "expected_source_sha256": "a" * 64,
                    "expected_repo_head": "b" * 40,
                    "idempotency_key": "operator-control-0001",
                },
            )],
        )

    def test_adapter_returns_capability_denied_without_write_scope(self):
        runtime = Edge1OperatorRuntime(client=FakeClient(), capabilities=CapabilityEvaluator(manifest=MANIFEST))
        adapter = MCPAdapter(runtime)
        result = adapter.call_tool(
            "edge1.telephony_console_reload",
            expected_pid=1,
            expected_source_sha256="a" * 64,
            expected_repo_head="b" * 40,
            idempotency_key="operator-control-0002",
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.payload, {"message": "capability_denied"})

    def test_reload_schema_has_no_generic_control_inputs(self):
        tool = next(item for item in TOOLS if item["name"] == "edge1.telephony_console_reload")
        props = set(tool["inputSchema"]["properties"])
        self.assertEqual(
            props,
            {"expected_pid", "expected_source_sha256", "expected_repo_head", "idempotency_key"},
        )
        for forbidden in {"service", "command", "argv", "path", "url", "host", "port", "sql", "environment"}:
            self.assertNotIn(forbidden, props)

    def test_typed_handler_rejects_extra_control_fields_before_execution(self):
        with self.assertRaises(TypedActionValidationError):
            run_typed_handler(
                "telephony_console_reload",
                {
                    "expected_pid": 123,
                    "expected_source_sha256": "a" * 64,
                    "expected_repo_head": "b" * 40,
                    "idempotency_key": "operator-control-0003",
                    "service": "asterisk.service",
                },
            )

    def test_broker_action_has_dedicated_gate_and_no_argv(self):
        action = ALLOWLIST["actions"]["telephony.console.reload_safe"]
        self.assertTrue(action["mutating"])
        self.assertEqual(action["typed_handler"], "telephony_console_reload")
        self.assertEqual(action["mutation_gate"], "telephony_safe_controls")
        self.assertNotIn("argv", action)
        self.assertNotIn("cwd", action)
        self.assertIn("Environment=EDGE1_OPS_MUTATIONS_ENABLED=false\n", OPS_SERVICE)
        self.assertIn("Environment=EDGE1_OPS_TELEPHONY_SAFE_CONTROLS_ENABLED=false\n", OPS_SERVICE)

    def test_idempotency_claim_is_fail_closed_until_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = pathlib.Path(tmp) / "audit.sqlite3"
            with mock.patch.object(operations_api, "DB_PATH", db_path):
                action = "telephony.console.reload_safe"
                key = "operator-control-0004"
                request_hash = "c" * 64
                self.assertIsNone(operations_api._idempotency_claim(action, key, request_hash))
                with self.assertRaises(TypedActionValidationError):
                    operations_api._idempotency_claim(action, key, request_hash)
                response = {
                    "action": action,
                    "status": "succeeded",
                    "event_id": "event-1",
                    "idempotent_replay": False,
                }
                operations_api._idempotency_complete(action, key, request_hash, response)
                replay = operations_api._idempotency_claim(action, key, request_hash)
                self.assertTrue(replay["idempotent_replay"])
                self.assertEqual(replay["event_id"], "event-1")
                with self.assertRaises(TypedActionValidationError):
                    operations_api._idempotency_claim(action, key, "d" * 64)

    def test_manifest_rejects_duplicate_tool_assignment(self):
        broken = json.loads(json.dumps(MANIFEST))
        broken["capabilities"]["edge1.messaging.read"]["tools"].append("edge1.identity")
        with self.assertRaises(CapabilityConfigurationError):
            CapabilityEvaluator(manifest=broken, scopes=frozenset())


if __name__ == "__main__":
    unittest.main()
