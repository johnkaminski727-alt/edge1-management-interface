#!/usr/bin/env python3
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'config/edge1_operator/navigation_registry.json'


class OperatorShellIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
        cls.accepted = {
            item['browser_route']
            for item in cls.registry['modules']
            if item.get('availability') == 'accepted_live' and item.get('browser_route')
        }

    def test_operations_center_uses_shell_and_unknown_is_not_good(self):
        text = (ROOT / 'src/web/operations-center/index.html').read_text(encoding='utf-8')
        self.assertIn('./operator-shell/shell.css', text)
        self.assertIn('./operator-shell/shell.js', text)
        self.assertIn('data-module="operations-center"', text)
        self.assertIn('const card=(title,value,state="neutral"', text)
        self.assertNotIn('const card=(title,value,state="good"', text)

    def test_communications_exposes_shell_without_mutation(self):
        page = (ROOT / 'src/web/communications/index.html').read_text(encoding='utf-8')
        server = (ROOT / 'server/unified_communications_server.py').read_text(encoding='utf-8')
        self.assertIn('./operator-shell/shell.css', page)
        self.assertIn('data-module="communications-workspace"', page)
        for route in ('/outbound-mail/', '/messaging-operations.html', '/telephony/', '/comms-relay/'):
            self.assertIn(route, page)
        for route in (
            '/communications/operator-shell/shell.js',
            '/communications/operator-shell/shell.css',
            '/communications/operator-shell/navigation.json',
        ):
            self.assertIn(route, server)
        self.assertIn('read_only_workspace', server)
        self.assertIn('Refusing non-loopback bind', server)
        self.assertNotIn('WWCXCommunicationsWorkspace/1.1', server)

    def test_security_inline_navigation_matches_accepted_registry(self):
        text = (ROOT / 'src/web/edge1-ops/security/index.html').read_text(encoding='utf-8')
        block = re.search(r'const acceptedNavigation=\[(.*?)\];', text, re.S)
        self.assertIsNotNone(block)
        routes = set(re.findall(r'"(/edge1-status/[^"\]]*|/edge1-status/)"', block.group(1)))
        self.assertEqual(routes, self.accepted)
        self.assertEqual(text.count('<style>'), 1)
        self.assertEqual(text.count('<script>'), 1)
        self.assertNotIn('/admin/ai/', block.group(1))
        self.assertNotIn('/communications/', block.group(1))
        self.assertNotIn('Store Admin', text)


if __name__ == '__main__':
    unittest.main()
