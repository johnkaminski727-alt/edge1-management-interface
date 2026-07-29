#!/usr/bin/env python3
"""Static validation for the bounded Security Correlation deployment path."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy" / "install-security-correlation-observability.sh"
SERVICE = ROOT / "deploy" / "systemd" / "wwcx-security-correlation.service"
PAGE = ROOT / "src" / "web" / "security" / "correlation.html"


class SecurityCorrelationDeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.installer = INSTALLER.read_text(encoding="utf-8")
        cls.service = SERVICE.read_text(encoding="utf-8")
        cls.page = PAGE.read_text(encoding="utf-8")

    def test_installer_has_preflight_backup_rollback_and_evidence(self):
        for token in (
            "branch --show-current",
            "status --porcelain",
            "merge-base --is-ancestor",
            "validate-security-correlation.sh",
            "backup_path",
            "restore_path",
            "trap rollback",
            "failure-systemd-status.txt",
            "failure-service-journal.txt",
            "rolled_back=true",
        ):
            self.assertIn(token, self.installer)

    def test_runtime_writes_only_to_scoped_data_directory(self):
        scoped = "/var/www/edge1-status/security/correlation/data"
        self.assertIn(f"--output {scoped}/security-correlation.json", self.service)
        self.assertIn(f"ReadWritePaths={scoped}", self.service)
        self.assertNotIn("ReadWritePaths=/var/www/edge1-status\n", self.service)
        self.assertIn("CapabilityBoundingSet=\n", self.service)
        self.assertIn("AmbientCapabilities=\n", self.service)
        self.assertIn('install -d -o root -g root -m 0755 "$DATA_ROOT"', self.installer)

    def test_compatibility_link_preserves_existing_read_endpoint(self):
        self.assertIn(
            'ln -sfn "security/correlation/data/security-correlation.json" "$LEGACY_LINK"',
            self.installer,
        )
        self.assertIn('curl -fsS --max-time 10 "$STATUS_URL/security-correlation.json"', self.installer)
        self.assertIn('const ENDPOINT="/edge1-status/security-correlation.json"', self.page)

    def test_deployment_verifies_privacy_contract(self):
        for token in (
            'document.get("read_only") is not True',
            '"packet_payloads_included", "credentials_included", "private_keys_included", "raw_logs_included"',
            'privacy.get("event_fields_minimized") is not True',
            "No IDS, DNS, firewall, proxy, routing, Fail2ban, or reputation-filter controls were changed.",
        ):
            self.assertIn(token, self.installer)

    def test_installer_has_no_control_plane_mutation(self):
        forbidden = (
            r"unbound-control",
            r"/etc/unbound",
            r"systemctl\s+(?:restart|reload|try-restart)\s+(?:unbound|suricata|fail2ban)",
            r"\bnft\b",
            r"\biptables\b",
            r"\bfirewall-cmd\b",
            r"suricata-update",
        )
        for pattern in forbidden:
            self.assertIsNone(re.search(pattern, self.installer, re.I), pattern)


if __name__ == "__main__":
    unittest.main()
