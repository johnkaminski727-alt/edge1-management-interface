#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import unittest

from server.edge1_operator_entrypoint import build_operator
from server.edge1_operator_transport import TransportRequest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "server/edge1_operator_mcp_protocol.py"
SERVICE_PATH = ROOT / "deploy/edge1-operations-api.service"
MCP_SERVICE_PATH = ROOT / "deploy/edge1-operator/edge1-operator-mcp.service"
SPEC = importlib.util.spec_from_file_location("edge1_operator_mcp_protocol", PROTOCOL_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

EXPECTED = (
    "edge1.identity",
    "edge1.health",
    "edge1.snapshot",
    "edge1.inventory",
    "edge1.services",
    "edge1.network_state",
    "edge1.disk_state",
    "edge1.bigbird_status",
    "edge1.operations_status",
    "edge1.apache_status",
    "edge1.asterisk_status",
    "edge1.telephony_status",
    "edge1.messaging_status",
    "edge1.time_authority_status",
    "edge1.git_state",
    "edge1.config_digest",
)


class FakeRuntime:
    def identity(self):
        return {"service": "edge1-operator"}

    def health(self):
        return {"status": "ok"}


class Edge1OperatorPublicContractTests(unittest.TestCase):
    def test_external_contract_is_exactly_sixteen_read_only_tools(self):
        names = tuple(tool["name"] for tool in MODULE.TOOLS)
        self.assertEqual(names, EXPECTED)
        self.assertEqual(MODULE.PUBLIC_EDGE1_TOOL_NAMES, EXPECTED)
        self.assertEqual(len(set(names)), 16)
        self.assertNotIn("agent.turn.status", names)
        self.assertNotIn("agent.turn.handoff", names)

    def test_all_public_tools_have_standard_bounded_read_annotations(self):
        expected = {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        }
        for tool in MODULE.TOOLS:
            with self.subTest(tool=tool["name"]):
                self.assertEqual(tool["access"], "read")
                self.assertEqual(tool["annotations"], expected)
                self.assertEqual(tool["inputSchema"]["additionalProperties"], False)

    def test_public_dispatch_rejects_internal_turn_tools_even_when_called_directly(self):
        operator, _runtime = build_operator(runtime=FakeRuntime(), turn_store=object())
        listed = operator.handle(TransportRequest(method="tools/list", payload={}))
        self.assertEqual(tuple(tool["name"] for tool in listed.result["tools"]), EXPECTED)

        cases = (
            ("agent.turn.status", {"task_id": "t", "conversation_id": "c"}),
            (
                "agent.turn.handoff",
                {
                    "task_id": "t",
                    "conversation_id": "c",
                    "requesting_agent": "fen",
                    "to_agent": "gus",
                    "expected_epoch": 0,
                    "idempotency_key": "k",
                },
            ),
        )
        for name, arguments in cases:
            with self.subTest(tool=name):
                response = operator.handle(
                    TransportRequest(
                        method="tools/call",
                        payload={"name": name, "arguments": arguments},
                    )
                )
                self.assertTrue(response.ok)
                self.assertEqual(
                    response.result,
                    {
                        "tool": name,
                        "status": "error",
                        "payload": {"message": "unknown_tool"},
                    },
                )

    def test_operations_api_allows_netlink_without_network_admin_capabilities(self):
        text = SERVICE_PATH.read_text(encoding="utf-8")
        families = next(
            line for line in text.splitlines() if line.startswith("RestrictAddressFamilies=")
        ).split("=", 1)[1].split()
        self.assertEqual(set(families), {"AF_UNIX", "AF_INET", "AF_INET6", "AF_NETLINK"})
        self.assertIn("CapabilityBoundingSet=\n", text)
        self.assertIn("AmbientCapabilities=\n", text)
        self.assertNotIn("CAP_NET_ADMIN", text)
        self.assertIn("Environment=EDGE1_OPS_MUTATIONS_ENABLED=false", text)

    def test_mcp_service_uses_dedicated_persistent_turn_state_without_weakening_sandbox(self):
        text = MCP_SERVICE_PATH.read_text(encoding="utf-8")
        self.assertIn("StateDirectory=edge1-operator-mcp\n", text)
        self.assertIn("StateDirectoryMode=0700\n", text)
        self.assertIn(
            "Environment=EDGE1_OPERATOR_TURN_STATE_ROOT=/var/lib/edge1-operator-mcp/turn-state\n",
            text,
        )
        self.assertIn("ProtectSystem=strict\n", text)
        self.assertIn("ReadOnlyPaths=/opt/edge1-management-interface\n", text)
        self.assertIn("UMask=0077\n", text)
        self.assertNotIn("ReadWritePaths=/opt/edge1-management-interface", text)


if __name__ == "__main__":
    unittest.main()
