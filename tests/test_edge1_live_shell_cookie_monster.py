from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
SOURCE = ROOT / 'tools/mcp/edge1-live-shell/src/index.js'


class CookieMonsterLiveShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE.read_text(encoding='utf-8')
        start = cls.text.index("server.registerTool('edge1_cookie_monster'")
        end = cls.text.index("server.registerTool('edge1_exec'", start)
        cls.block = cls.text[start:end]

    def test_mutation_gate_defaults_off(self):
        self.assertIn("process.env.EDGE1_ALLOW_COOKIE_MONSTER === '1'", self.text)
        self.assertIn('EDGE1_ALLOW_COOKIE_MONSTER=0', self.block)

    def test_target_sha_is_explicit_and_strict(self):
        self.assertIn('EDGE1_COOKIE_MONSTER_TARGET_SHA', self.text)
        self.assertIn('/^[0-9a-f]{40}$/.test(COOKIE_MONSTER_TARGET_SHA)', self.text)
        self.assertIn('must be an exact 40-character Git commit SHA', self.block)

    def test_tool_accepts_only_fixed_action_enum(self):
        self.assertIn("z.enum(['preflight', 'sync_sources', 'activate', 'rollback_last'])", self.block)
        self.assertNotIn('command: z.', self.block)
        self.assertNotIn('path: z.', self.block)
        self.assertNotIn('url: z.', self.block)

    def test_sync_is_clean_main_pinned_fast_forward_only(self):
        command_start = self.text.index("if (action === 'sync_sources')")
        command_end = self.text.index("if (action === 'activate')", command_start)
        command = self.text[command_start:command_end]
        self.assertIn('symbolic-ref --short HEAD', command)
        self.assertIn('status --porcelain', command)
        self.assertIn('fetch --prune origin', command)
        self.assertIn('cat-file -e "$target^{commit}"', command)
        self.assertIn('merge-base --is-ancestor "$target" origin/main', command)
        self.assertIn('merge --ff-only "$target"', command)
        self.assertIn('test "$after" = "$target"', command)
        self.assertNotIn('merge --ff-only origin/main', command)
        for forbidden in (' reset ', ' clean ', ' stash ', ' rebase ', ' checkout ', ' push '):
            self.assertNotIn(forbidden, command)

    def test_activation_requires_pinned_head_and_fixed_script(self):
        self.assertIn('/deploy/cookie_monster_edge1_activate.py', self.text)
        self.assertIn('sudo -n /usr/bin/python3', self.text)
        command_start = self.text.index("if (action === 'activate')")
        command_end = self.text.index("if (action === 'rollback_last')", command_start)
        command = self.text[command_start:command_end]
        self.assertIn('rev-parse HEAD', command)
        self.assertIn('= "$target"', command)
        self.assertIn('--apply', command)
        self.assertIn("if (action === 'rollback_last')", self.text)
        self.assertIn('--rollback-last', self.text)

    def test_raw_shell_remains_separately_disabled(self):
        self.assertIn("process.env.EDGE1_ENABLE_RAW_SHELL === '1'", self.text)
        self.assertIn('Raw shell is disabled by policy (EDGE1_ENABLE_RAW_SHELL=0).', self.text)
        self.assertNotIn('ENABLE_RAW_SHELL', self.block)


if __name__ == '__main__':
    unittest.main()
