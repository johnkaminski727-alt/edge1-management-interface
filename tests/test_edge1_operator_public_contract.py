#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "server/edge1_operator_mcp_protocol.py"
SERVICE_PATH = ROOT / "deploy/edge1-operations-api.service"
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


if __name__ == "__main__":
    unittest.main()
