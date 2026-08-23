from __future__ import annotations
import pathlib
import unittest
from unittest.mock import patch
from server import ava_operator_broker as broker

class AvaOperatorBrokerTests(unittest.TestCase):
    def setUp(self):
        audit = patch.object(broker, "_audit")
        audit.start()
        self.addCleanup(audit.stop)

    def test_edge1_read_maps_only_to_named_operator_tools(self):
        with patch.object(broker, "_mcp", return_value={"status":"ok"}) as call:
            value = broker.invoke("edge1.read.health", {}, False)
        self.assertEqual(value["status"], "completed")
        self.assertEqual(call.call_args.args[1], "edge1.health")

    def test_business159_read_uses_fixed_command(self):
        with patch.object(broker, "_business159", return_value={"ok":True}) as call:
            value = broker.invoke("business159.read.git", {}, False)
        self.assertEqual(value["status"], "completed")
        self.assertIn("git rev-parse", call.call_args.args[0])

    def test_raw_shell_denied_without_confirmation(self):
        with patch.object(broker, "_mcp") as call:
            value = broker.invoke("edge1.shell.exec", {"command":"id"}, False)
        self.assertEqual(value["status"], "denied")
        call.assert_not_called()

    def test_raw_shell_reaches_agent_shell_only_when_confirmed(self):
        with patch.object(broker, "_mcp", return_value={"ok":True}) as call:
            value = broker.invoke("edge1.shell.exec", {"command":"id"}, True)
        self.assertEqual(value["status"], "completed")
        self.assertEqual(call.call_args.args[0], broker.EDGE1_SHELL_URL)
        self.assertEqual(call.call_args.args[1], "edge1_agent_exec")

    def test_service_repair_is_allowlisted(self):
        with patch.object(broker, "_mcp", return_value={"ok":True}):
            self.assertEqual(broker.invoke("edge1.service.repair", {"service":"bigbird-ai-gateway.service","action":"status"}, False)["status"], "completed")
        self.assertEqual(broker.invoke("edge1.service.repair", {"service":"ssh.service","action":"restart"}, False)["status"], "error")

    def test_unknown_capability_fails_closed(self):
        self.assertEqual(broker.invoke("anything.exec", {}, True)["status"], "denied")

if __name__ == "__main__": unittest.main()
