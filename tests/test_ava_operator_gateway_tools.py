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
    def test_shell_tools_absent_by_default_and_independent(self):
        self.assertNotIn('edge1_unrestricted_shell',{x['name'] for x in tools.tool_definitions()})
        self.assertIn('edge1_unrestricted_shell',{x['name'] for x in tools.tool_definitions(shell_hosts={'edge1'})})
        self.assertNotIn('business159_unrestricted_shell',{x['name'] for x in tools.tool_definitions(shell_hosts={'edge1'})})
        self.assertIn('business159_unrestricted_shell',{x['name'] for x in tools.tool_definitions(shell_hosts={'business159'})})
    def test_active_shell_hosts_uses_broker_gate(self):
        def call(_cap,args,**_kw):
            return {'result':{'enabled':args['host']=='edge1'}}
        with patch.object(tools,'broker_call',side_effect=call):
            self.assertEqual(tools.active_shell_hosts({'edge1','business159'}),{'edge1'})
    def test_read_maps_to_broker_capability(self):
        with patch.object(tools,'broker_call',return_value={'status':'completed'}) as call:
            tools.execute_tool('business159_operator_read',{'resource':'git'})
        self.assertEqual(call.call_args.args[0],'business159.read.git')
    def test_shell_execution_requires_server_active_host(self):
        with self.assertRaises(tools.OperatorGatewayError):
            tools.execute_tool('edge1_unrestricted_shell',{'command':'id'},shell_hosts=set())
        with patch.object(tools,'broker_call',return_value={'status':'completed'}) as call:
            tools.execute_tool('edge1_unrestricted_shell',{'command':'id'},shell_hosts={'edge1'})
        self.assertEqual(call.call_args.args[0],'edge1.shell.exec'); self.assertTrue(call.call_args.kwargs['confirmed'])
    def test_action_rejected_without_server_scope(self):
        with self.assertRaises(tools.OperatorGatewayError):
            tools.execute_tool('edge1_service_repair',{'service':'bigbird-ai-gateway.service','action':'status'},allow_actions=False)

if __name__=='__main__': unittest.main()
