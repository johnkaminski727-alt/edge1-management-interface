#!/usr/bin/env python3
"""Static validation for the bounded Network Defense deployment path."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy" / "install-network-defense-observability.sh"
SERVICE = ROOT / "deploy" / "systemd" / "wwcx-network-defense.service"
OPERATIONS = ROOT / "src" / "web" / "operations-center" / "index.html"
NETWORK = ROOT / "src" / "web" / "network-defense" / "index.html"
CORRELATION = ROOT / "src" / "web" / "security" / "correlation.html"


class NetworkDefenseDeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.installer = INSTALLER.read_text(encoding="utf-8")
        cls.service = SERVICE.read_text(encoding="utf-8")
        cls.operations = OPERATIONS.read_text(encoding="utf-8")
        cls.network = NETWORK.read_text(encoding="utf-8")
        cls.correlation = CORRELATION.read_text(encoding="utf-8")

    def test_installer_has_preflight_validation_and_rollback(self):
        for token in (
            "branch --show-current",
            "status --porcelain",
            "merge-base --is-ancestor",
            "validate-network-defense.sh",
            "backup_path",
            "restore_path",
            "trap rollback",
            "rolled_back=true",
        ):
            self.assertIn(token, self.installer)

    def test_rollback_captures_service_failure_evidence(self):
        for token in (
            "failure-systemd-status.txt",
            "failure-service-journal.txt",
            'journalctl -u "$SERVICE" -n 100',
            "Failure evidence:",
        ):
            self.assertIn(token, self.installer)

    def test_installer_publishes_only_observability_assets(self):
        for token in (
            "/var/www/edge1-status",
            "wwcx-network-defense.service",
            "wwcx-network-defense.timer",
            "src/web/operations-center/index.html",
            "src/web/network-defense/index.html",
            "src/web/security/correlation.html",
            "network-defense.json",
        ):
            self.assertIn(token, self.installer)

    def test_scoped_data_directory_preserves_empty_capability_set(self):
        for token in (
            'DATA_ROOT=${EDGE1_NETWORK_DEFENSE_DATA_ROOT:-$STATUS_ROOT/network-defense/data}',
            'install -d -o root -g root -m 0755 "$DATA_ROOT"',
            'curl -fsS --max-time 10 "$STATUS_URL/network-defense/data/network-defense.json"',
        ):
            self.assertIn(token, self.installer)
        self.assertIn(
            "--output /var/www/edge1-status/network-defense/data/network-defense.json",
            self.service,
        )
        self.assertIn(
            "ReadWritePaths=/var/www/edge1-status/network-defense/data",
            self.service,
        )
        self.assertNotIn("ReadWritePaths=/var/www/edge1-status\n", self.service)
        self.assertIn("CapabilityBoundingSet=\n", self.service)
        self.assertIn("AmbientCapabilities=\n", self.service)

    def test_installer_has_no_resolver_or_traffic_control_mutation(self):
        forbidden = (
            r"unbound-control",
            r"/etc/unbound",
            r"systemctl\s+(?:restart|reload|try-restart)\s+unbound",
            r"build-dns-defense-staging\.sh",
            r"/etc/wwcx/dns-defense/policy\.json",
            r"\bnft\b",
            r"\biptables\b",
            r"\bfirewall-cmd\b",
        )
        for pattern in forbidden:
            self.assertIsNone(re.search(pattern, self.installer, re.I), pattern)

    def test_dns_aware_exporter_is_the_runtime_entrypoint(self):
        self.assertIn("server/network_defense_dns_exporter.py", self.service)
        self.assertNotRegex(self.service, r"ExecStart=.*server/network_defense_exporter\.py(?:\s|$)")

    def test_module_navigation_uses_authoritative_status_root(self):
        expected = (
            "/edge1-status/",
            "/edge1-status/security/",
            "/edge1-status/security/correlation.html",
            "/edge1-status/network-defense/",
        )
        for token in expected:
            self.assertIn(token, self.operations)
            self.assertIn(token, self.network)
            self.assertIn(token, self.correlation)

    def test_deployment_verifies_read_only_dns_contract(self):
        for token in (
            'traffic_controls_changed") is not False',
            'enforcement_enabled", "enforcement_verified", "traffic_controls_changed"',
            'requires_explicit_activation") is not True',
            "DNS enforcement remains disabled",
            'bash "$REPO_ROOT/tools/networking/validate-network-defense.sh"',
        ):
            self.assertIn(token, self.installer)


if __name__ == "__main__":
    unittest.main()
