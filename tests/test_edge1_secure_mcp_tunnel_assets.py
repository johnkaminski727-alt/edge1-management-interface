import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
PROFILE = (ROOT / "deploy/edge1-tunnel/tunnel-client.yaml").read_text(encoding="utf-8")
LAUNCHER = (ROOT / "deploy/edge1-tunnel/edge1-secure-mcp-tunnel.sh").read_text(encoding="utf-8")
SERVICE = (ROOT / "deploy/edge1-tunnel/edge1-secure-mcp-tunnel.service").read_text(encoding="utf-8")
INSTALLER = (ROOT / "deploy/edge1-tunnel/install-edge1-secure-mcp-tunnel.sh").read_text(encoding="utf-8")


class SecureMcpTunnelAssetsTests(unittest.TestCase):
    def test_profile_targets_only_loopback_operator(self):
        self.assertIn("url: http://127.0.0.1:8102/mcp", PROFILE)
        self.assertIn("listen_addr: 127.0.0.1:0", PROFILE)
        self.assertNotIn("0.0.0.0", PROFILE)
        self.assertNotIn("edge1.ww.cx", PROFILE)

    def test_profile_keeps_secrets_out_of_yaml(self):
        self.assertIn("api_key: file:/etc/edge1-tunnel/runtime-api-key", PROFILE)
        self.assertIn("Authorization: env:EDGE1_MCP_AUTHORIZATION", PROFILE)
        self.assertEqual(PROFILE.count("Authorization: env:EDGE1_MCP_AUTHORIZATION"), 2)
        for token in ("Bearer ", "sk-", "mcp-token="):
            with self.subTest(token=token):
                self.assertNotIn(token, PROFILE)

    def test_profile_uses_managed_companion_runtime(self):
        self.assertIn("cloudflared:\n  managed: true", PROFILE)
        self.assertIn('"$BINARY" cloudflared version', INSTALLER)
        self.assertIn("complete official release bundle", INSTALLER)

    def test_launcher_reuses_existing_operator_token_without_persistent_copy(self):
        self.assertIn("/etc/edge1-operator/mcp-token", LAUNCHER)
        self.assertIn('export EDGE1_MCP_AUTHORIZATION="Bearer $MCP_TOKEN"', LAUNCHER)
        self.assertIn('unset TUNNEL_ID MCP_TOKEN', LAUNCHER)
        self.assertNotIn("cp ", LAUNCHER)
        self.assertNotIn("tee ", LAUNCHER)

    def test_service_runs_as_bounded_operator_and_preserves_hardening(self):
        required = (
            "User=edge1-operator",
            "Group=edge1-operator",
            "NoNewPrivileges=true",
            "ProtectSystem=strict",
            "ProtectHome=true",
            "CapabilityBoundingSet=",
            "AmbientCapabilities=",
            "Requires=edge1-operator-mcp.service",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, SERVICE)

    def test_staging_never_enables_or_starts_tunnel(self):
        self.assertIn('systemctl disable "$SERVICE"', INSTALLER)
        self.assertIn('systemctl stop "$SERVICE"', INSTALLER)
        self.assertIn("service remains disabled/inactive", INSTALLER)
        self.assertNotIn("enable --now", INSTALLER)

    def test_no_network_or_auth_broadening_primitives(self):
        combined = "\n".join((PROFILE, LAUNCHER, SERVICE, INSTALLER))
        forbidden = (
            "iptables",
            "nft add",
            "ufw ",
            "firewall-cmd",
            "usermod",
            "sudoers",
            "chmod 777",
            "0.0.0.0:8102",
            "EDGE1_OPERATOR_MCP_HOST=0.0.0.0",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
