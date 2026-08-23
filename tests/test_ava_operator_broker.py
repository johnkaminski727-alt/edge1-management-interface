from __future__ import annotations
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from server import ava_operator_broker as broker

class AvaOperatorBrokerTests(unittest.TestCase):
    def setUp(self):
        audit = patch.object(broker, "_audit")
        audit.start(); self.addCleanup(audit.stop)
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        gate=patch.object(broker,"SHELL_GATE_DIR",Path(self.temp.name)); gate.start(); self.addCleanup(gate.stop)

    def enable_gate(self, host: str, seconds: int = 60):
        path=broker.SHELL_GATE_DIR/f"{host}.json"
        path.write_text(json.dumps({"expires_at_unix":int(time.time())+seconds,"actor":"test","ticket":"T1"}),encoding="utf-8")
        path.chmod(0o600)

    def test_mcp_decoder_accepts_json_and_sse(self):
        payload={"result":{"structuredContent":{"ok":True}}}
        raw=json.dumps(payload).encode()
        self.assertEqual(broker._decode_mcp_payload(raw,"application/json"),payload)
        sse=("event: message\n"+"data: "+json.dumps(payload)+"\n\n").encode()
        self.assertEqual(broker._decode_mcp_payload(sse,"text/event-stream"),payload)

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
        self.enable_gate("edge1")
        with patch.object(broker, "_mcp") as call:
            value = broker.invoke("edge1.shell.exec", {"command":"id"}, False)
        self.assertEqual(value["status"], "denied"); call.assert_not_called()

    def test_raw_shell_denied_when_gate_disabled(self):
        with patch.object(broker, "_mcp") as call:
            value = broker.invoke("edge1.shell.exec", {"command":"id"}, True)
        self.assertEqual(value["status"], "denied")
        self.assertEqual(value["decision"]["reason"], "shell_gate_disabled")
        call.assert_not_called()

    def test_raw_shell_reaches_agent_shell_only_when_gate_and_confirmation_present(self):
        self.enable_gate("edge1")
        with patch.object(broker, "_mcp", return_value={"ok":True}) as call:
            value = broker.invoke("edge1.shell.exec", {"command":"id"}, True)
        self.assertEqual(value["status"], "completed")
        self.assertEqual(call.call_args.args[0], broker.EDGE1_SHELL_URL)
        self.assertEqual(call.call_args.args[1], "edge1_agent_exec")

    def test_business159_shell_requires_its_independent_gate(self):
        self.enable_gate("business159")
        with patch.object(broker,"_business159",return_value={"ok":True}) as call:
            value=broker.invoke("business159.shell.exec",{"command":"id"},True)
        self.assertEqual(value["status"],"completed"); call.assert_called_once()

    def test_gate_status_is_read_only_and_expiry_aware(self):
        self.enable_gate("edge1",seconds=60)
        value=broker.invoke("shell.gate.status",{"host":"edge1"},False)
        self.assertTrue(value["result"]["enabled"])
        (broker.SHELL_GATE_DIR/"edge1.json").write_text(json.dumps({"expires_at_unix":int(time.time())-1}),encoding="utf-8")
        (broker.SHELL_GATE_DIR/"edge1.json").chmod(0o600)
        value=broker.invoke("shell.gate.status",{"host":"edge1"},False)
        self.assertFalse(value["result"]["enabled"])

    def test_service_repair_is_allowlisted(self):
        with patch.object(broker, "_mcp", return_value={"ok":True}):
            self.assertEqual(broker.invoke("edge1.service.repair", {"service":"bigbird-ai-gateway.service","action":"status"}, False)["status"], "completed")
        self.assertEqual(broker.invoke("edge1.service.repair", {"service":"ssh.service","action":"restart"}, False)["status"], "error")

    def test_unknown_capability_fails_closed(self):
        self.assertEqual(broker.invoke("anything.exec", {}, True)["status"], "denied")

if __name__ == "__main__": unittest.main()
