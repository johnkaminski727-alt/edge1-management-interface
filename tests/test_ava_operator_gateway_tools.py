from __future__ import annotations
import unittest
from unittest.mock import patch
from server import ava_operator_gateway_tools as tools

class Tests(unittest.TestCase):
    def test_read_tools_are_always_typed(self):
        defs=tools.tool_definitions()
        self.assertEqual({x['name'] for x in defs},{'edge1_operator_read','business159_operator_read'})
        self.assertTrue(all(x['parameters']['additionalProperties'] is False for x in defs))
    def test_actions_absent_by_default(self):
        self.assertNotIn('edge1_service_repair',{x['name'] for x in tools.tool_definitions()})
        self.assertIn('edge1_service_repair',{x['name'] for x in tools.tool_definitions(allow_actions=True)})
    def test_read_maps_to_broker_capability(self):
        with patch.object(tools,'broker_call',return_value={'status':'completed'}) as call:
            tools.execute_tool('business159_operator_read',{'resource':'git'})
        self.assertEqual(call.call_args.args[0],'business159.read.git')
    def test_action_rejected_without_server_scope(self):
        with self.assertRaises(tools.OperatorGatewayError):
            tools.execute_tool('edge1_service_repair',{'service':'bigbird-ai-gateway.service','action':'status'},allow_actions=False)

if __name__=='__main__': unittest.main()
