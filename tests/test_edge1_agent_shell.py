from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
SOURCE = ROOT / 'tools/mcp/edge1-agent-shell/src/index.js'
README = ROOT / 'tools/mcp/edge1-agent-shell/README.md'
UNIT = ROOT / 'deploy/edge1-agent-shell/edge1-agent-shell.service'
INSTALLER = ROOT / 'deploy/edge1-agent-shell/install-edge1-agent-shell.sh'
TUNNEL = ROOT / 'deploy/edge1-tunnel/tunnel-client.yaml'


class Edge1AgentShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding='utf-8')
        cls.readme = README.read_text(encoding='utf-8')
        cls.unit = UNIT.read_text(encoding='utf-8')
        cls.installer = INSTALLER.read_text(encoding='utf-8')
        cls.tunnel = TUNNEL.read_text(encoding='utf-8')

    def test_full_mode_is_first_class(self):
        self.assertIn("EDGE1_AGENT_SHELL_MODE || 'full'", self.source)
        self.assertIn("['full', 'read-only']", self.source)
        self.assertIn('There are no per-service, per-directory or per-command allowlists in full mode.', self.readme)

    def test_full_capability_tools_exist(self):
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
            self.assertIn(f"server.registerTool('{name}'", self.source)

    def test_exec_is_arbitrary_and_not_allowlisted(self):
        block = self.source[self.source.index("server.registerTool('edge1_agent_exec'"):]
        block = block[:block.index("server.registerTool('edge1_agent_file_stat'")]
        self.assertIn("spawn('/bin/sh', ['-lc', command]", self.source)
        self.assertNotIn('ALLOWED_COMMAND', block)
        self.assertNotIn('allowlist', block.lower())
        self.assertIn('command: z.string().min(1).max(65536)', block)

    def test_files_cover_read_write_update_and_management(self):
        self.assertIn("z.enum(['create', 'replace', 'append', 'write_at'])", self.source)
        self.assertIn('expected_sha256', self.source)
        self.assertIn('atomicReplace', self.source)
        self.assertIn("z.enum(['mkdir', 'remove', 'move', 'copy', 'chmod', 'chown', 'symlink', 'hardlink'])", self.source)

    def test_http_is_loopback_and_bearer_protected(self):
        self.assertIn("EDGE1_AGENT_SHELL_HOST || '127.0.0.1'", self.source)
        self.assertIn("EDGE1_AGENT_SHELL_PORT || 8114", self.source)
        self.assertIn('Edge1 Agent Shell must bind to loopback only', self.source)
        self.assertIn('tokenMatches(req.headers.authorization, token)', self.source)
        self.assertIn("res.writeHead(401", self.source)
        self.assertIn("res.writeHead(403", self.source)

    def test_service_is_explicitly_root_capable_and_loopback(self):
        self.assertIn('User=root', self.unit)
        self.assertIn('Group=root', self.unit)
        self.assertIn('EDGE1_AGENT_SHELL_MODE=full', self.unit)
        self.assertIn('EDGE1_AGENT_SHELL_HOST=127.0.0.1', self.unit)
        self.assertIn('EDGE1_AGENT_SHELL_PORT=8114', self.unit)
        self.assertIn('NoNewPrivileges=false', self.unit)

    def test_installer_is_dry_run_and_has_rollback(self):
        self.assertIn('APPLY=0', self.installer)
        self.assertIn('--apply', self.installer)
        self.assertIn('dry-run only; pass --apply to install', self.installer)
        self.assertIn('rollback()', self.installer)
        self.assertIn('wwcx-edge1-agent-shell-', self.installer)
        self.assertIn('127.0.0.1:$PORT/healthz', self.installer)
        self.assertIn('listener verification failed', self.installer)

    def test_existing_tunnel_carries_second_channel(self):
        self.assertIn('channel: main', self.tunnel)
        self.assertIn('url: http://127.0.0.1:8102/mcp', self.tunnel)
        self.assertIn('channel: agent-shell', self.tunnel)
        self.assertIn('url: http://127.0.0.1:8114/mcp', self.tunnel)
        self.assertIn('Authorization: env:EDGE1_MCP_AUTHORIZATION', self.tunnel)

    def test_audit_does_not_log_command_text_or_file_content(self):
        self.assertIn('command_sha256', self.source)
        audit_start = self.source.index('function audit(')
        audit_end = self.source.index('function shellResult(', audit_start)
        audit_block = self.source[audit_start:audit_end]
        self.assertNotIn('command:', audit_block)
        self.assertNotIn('data:', audit_block)
        self.assertNotIn('stdin', audit_block)


if __name__ == '__main__':
    unittest.main()
