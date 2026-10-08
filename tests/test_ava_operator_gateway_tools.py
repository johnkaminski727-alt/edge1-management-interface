from __future__ import annotations
import unittest
from unittest import mock

from server import ava_operator_gateway_tools as tools


class Tests(unittest.TestCase):
    def test_read_tools_are_mcp_typed_and_legacy_names_are_not_advertised(self):
        defs=tools.tool_definitions()
        names={x['name'] for x in defs}
        self.assertEqual(names,{'edge1_mcp_read','business159_mcp_read'})
        self.assertFalse(names & set(tools.LEGACY_TOOL_ALIASES))
        for item in defs:
            self.assertEqual(item['type'],'function')
            self.assertTrue(item['strict'])
            self.assertFalse(item['parameters']['additionalProperties'])

    def test_actions_absent_by_default(self):
        self.assertNotIn('edge1_mcp_service_action',{x['name'] for x in tools.tool_definitions()})
        self.assertIn('edge1_mcp_service_action',{x['name'] for x in tools.tool_definitions(allow_actions=True)})

    def test_shell_tools_absent_by_default_and_independent(self):
        self.assertNotIn('edge1_mcp_shell',{x['name'] for x in tools.tool_definitions()})
        self.assertIn('edge1_mcp_shell',{x['name'] for x in tools.tool_definitions(shell_hosts={'edge1'})})
        self.assertNotIn('business159_mcp_shell',{x['name'] for x in tools.tool_definitions(shell_hosts={'edge1'})})
        self.assertIn('business159_mcp_shell',{x['name'] for x in tools.tool_definitions(shell_hosts={'business159'})})

    def test_business159_read_maps_to_broker_capability(self):
        with mock.patch.object(tools,'broker_call',return_value={'status':'completed'}) as call:
            out=tools.execute_tool('business159_mcp_read',{'resource':'git'})
        self.assertEqual(out['status'],'completed')
        call.assert_called_once_with('business159.read.git')

    def test_legacy_read_alias_is_accepted_but_not_advertised(self):
        with mock.patch.object(tools,'broker_call',return_value={'status':'completed'}) as call:
            out=tools.execute_tool('edge1_operator_read',{'resource':'health'})
        self.assertEqual(out['status'],'completed')
        call.assert_called_once_with('edge1.read.health')

    def test_shell_requires_active_host(self):
        with self.assertRaises(tools.OperatorGatewayError):
            tools.execute_tool('edge1_mcp_shell',{'command':'id'},shell_hosts=set())
        with mock.patch.object(tools,'broker_call',return_value={'status':'completed'}) as call:
            tools.execute_tool('edge1_mcp_shell',{'command':'id'},shell_hosts={'edge1'})
        self.assertEqual(call.call_args.args[0],'edge1.shell.exec')
        self.assertTrue(call.call_args.kwargs['confirmed'])

    def test_service_action_requires_action_scope(self):
        with self.assertRaises(tools.OperatorGatewayError):
            tools.execute_tool('edge1_mcp_service_action',{'service':'bigbird-ai-gateway.service','action':'status'},allow_actions=False)
        with mock.patch.object(tools,'broker_call',return_value={'status':'completed'}) as call:
            tools.execute_tool('edge1_mcp_service_action',{'service':'bigbird-ai-gateway.service','action':'status'},allow_actions=True)
        call.assert_called_once_with('edge1.service.repair',{'service':'bigbird-ai-gateway.service','action':'status'})


if __name__=='__main__':
    unittest.main()
