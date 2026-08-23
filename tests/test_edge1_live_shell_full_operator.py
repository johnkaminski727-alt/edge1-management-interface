from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
SOURCE = ROOT / 'tools/mcp/edge1-live-shell/src/index.js'


class Edge1LiveShellFullOperatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE.read_text(encoding='utf-8')

    def test_capability_discovery_exists(self):
        self.assertIn("server.registerTool('edge1_capabilities'", self.text)
        self.assertIn('fileMutations: ENABLE_FILE_MUTATIONS', self.text)
        self.assertIn('sudoShell: ENABLE_RAW_SHELL && ALLOW_SUDO_SHELL', self.text)

    def test_structured_filesystem_surface_is_full_crud_style(self):
        self.assertIn("server.registerTool('edge1_fs'", self.text)
        self.assertIn("z.enum(['stat', 'list', 'read', 'write', 'append', 'mkdir', 'move', 'copy', 'remove', 'chmod'])", self.text)
        self.assertIn("process.env.EDGE1_ENABLE_FILE_MUTATIONS === '1'", self.text)
        self.assertIn('expectedSha256', self.text)
        self.assertIn('backup', self.text)
        self.assertIn('os.replace(tmp,p)', self.text)
        self.assertIn("'.agent-backup-'", self.text)

    def test_read_does_not_require_mutation_gate(self):
        self.assertIn("const readOnly = new Set(['stat', 'list', 'read']);", self.text)
        self.assertIn("if (!readOnly.has(args.action) && !ENABLE_FILE_MUTATIONS)", self.text)

    def test_raw_shell_supports_cwd_stdin_and_optional_sudo(self):
        start = self.text.index("server.registerTool('edge1_exec'")
        block = self.text[start:]
        self.assertIn('cwd: z.string()', block)
        self.assertIn('stdin: z.string()', block)
        self.assertIn('sudo: z.boolean()', block)
        self.assertIn("process.env.EDGE1_ALLOW_SUDO_SHELL === '1'", self.text)
        self.assertIn("sudo -n /bin/sh -lc", block)
        self.assertIn("runSsh(remote, stdin)", block)

    def test_ssh_transport_keeps_host_key_verification_and_batch_auth(self):
        self.assertIn("'BatchMode=yes'", self.text)
        self.assertIn("'StrictHostKeyChecking=yes'", self.text)
        self.assertIn("spawn('ssh'", self.text)

    def test_output_and_file_sizes_remain_bounded(self):
        self.assertIn('MAX_OUTPUT_BYTES', self.text)
        self.assertIn('MAX_FILE_BYTES', self.text)
        self.assertIn('file exceeds maxBytes', self.text)


if __name__ == '__main__':
    unittest.main()
