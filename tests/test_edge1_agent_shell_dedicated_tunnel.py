import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = (ROOT / "deploy/edge1-agent-shell-tunnel/tunnel-client.yaml").read_text()
UNIT = (ROOT / "deploy/edge1-agent-shell-tunnel/edge1-agent-shell-secure-mcp-tunnel.service").read_text()
INSTALLER = (ROOT / "deploy/edge1-agent-shell-tunnel/install-edge1-agent-shell-secure-mcp-tunnel.sh").read_text()


class DedicatedAgentShellTunnelTests(unittest.TestCase):
    def test_routes_only_agent_shell_as_main(self):
        self.assertIn("- channel: main\n      url: http://127.0.0.1:8114/mcp", CONFIG)
        self.assertNotIn("127.0.0.1:8102", CONFIG)

    def test_reuses_existing_secret_boundaries(self):
        self.assertIn("api_key: file:/etc/edge1-tunnel/runtime-api-key", CONFIG)
        self.assertIn("Authorization: env:EDGE1_MCP_AUTHORIZATION", CONFIG)
        self.assertIn("EDGE1_OPERATOR_MCP_TOKEN_FILE=/etc/edge1-operator/mcp-token", UNIT)
        self.assertNotIn('> "$API_KEY_FILE"', INSTALLER)
        self.assertNotIn('tee "$API_KEY_FILE"', INSTALLER)

    def test_has_independent_runtime_paths(self):
        self.assertIn("/run/edge1-agent-shell-secure-mcp-tunnel/health-url", CONFIG)
        self.assertIn("/run/edge1-agent-shell-secure-mcp-tunnel/tunnel-client.pid", CONFIG)
        self.assertIn("RuntimeDirectory=edge1-agent-shell-secure-mcp-tunnel", UNIT)

    def test_preserves_human_enrollment_boundary(self):
        self.assertIn("ETC_DIR=/etc/edge1-agent-shell-tunnel", INSTALLER)
        self.assertIn('TUNNEL_ID_FILE="$ETC_DIR/tunnel-id"', INSTALLER)
        self.assertIn("never creates, prints, copies, or commits the tunnel", INSTALLER)
        self.assertNotIn("tunnel_6a", INSTALLER)

    def test_preserves_read_only_operator(self):
        self.assertIn("edge1-secure-mcp-tunnel.service", INSTALLER)
        self.assertIn("edge1-operator-mcp.service", INSTALLER)


if __name__ == "__main__":
    unittest.main()
