import json
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
PLUGIN = ROOT / 'plugins/edge1-agent-shell/.codex-plugin/plugin.json'
APP = ROOT / 'plugins/edge1-agent-shell/.app.json'
SKILL = ROOT / 'plugins/edge1-agent-shell/skills/wwcx-edge1-agent-shell-router/SKILL.md'
OPENAI = ROOT / 'plugins/edge1-agent-shell/skills/wwcx-edge1-agent-shell-router/agents/openai.yaml'
MARKETPLACE = ROOT / '.agents/plugins/marketplace.json'


class Edge1AgentShellPluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = json.loads(PLUGIN.read_text(encoding='utf-8'))
        cls.app = json.loads(APP.read_text(encoding='utf-8'))
        cls.skill = SKILL.read_text(encoding='utf-8')
        cls.openai = OPENAI.read_text(encoding='utf-8')
        cls.marketplace = json.loads(MARKETPLACE.read_text(encoding='utf-8'))

    def test_plugin_has_distinct_high_authority_identity(self):
        self.assertEqual(self.plugin['name'], 'wwcx-edge1-agent-shell')
        self.assertEqual(self.plugin['interface']['displayName'], 'WW.CX Edge1 Agent Shell')
        self.assertIn('read/write/update/service/shell', self.plugin['description'])

    def test_plugin_reuses_existing_private_edge1_app(self):
        self.assertEqual(
            self.app['apps']['edge1']['id'],
            'asdk_app_6a84c1e678708191b3e8f00e886be802',
        )
        self.assertIn('value: edge1', self.openai)
        self.assertIn('allow_implicit_invocation: true', self.openai)

    def test_router_knows_all_agent_shell_tools(self):
        for name in (
            'edge1_agent_identity',
            'edge1_agent_capabilities',
            'edge1_agent_exec',
            'edge1_agent_file_stat',
            'edge1_agent_file_read',
            'edge1_agent_file_write',
            'edge1_agent_file_patch',
            'edge1_agent_file_manage',
            'edge1_agent_service',
        ):
            self.assertIn(name, self.skill)

    def test_router_does_not_reintroduce_fake_allowlists(self):
        self.assertIn('do not invent additional per-command, per-service, or per-directory approval gates', self.skill)
        self.assertIn('mode=full', self.skill)
        self.assertIn('Do not claim an Agent Shell operation ran', self.skill)

    def test_marketplace_publishes_distinct_package(self):
        entries = {item['name']: item for item in self.marketplace['plugins']}
        self.assertIn('edge1-agent-shell', entries)
        self.assertEqual(entries['edge1-agent-shell']['source']['path'], './plugins/edge1-agent-shell')
        self.assertEqual(entries['edge1-agent-shell']['policy']['installation'], 'AVAILABLE')
        self.assertEqual(entries['edge1-agent-shell']['policy']['authentication'], 'ON_INSTALL')


if __name__ == '__main__':
    unittest.main()
