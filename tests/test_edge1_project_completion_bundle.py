#!/usr/bin/env python3
"""Static validation for the bounded Edge1 project-completion operator bundle."""

from __future__ import annotations

import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ACTIVATION = ROOT / "deploy" / "activate-network-defense-freshness.sh"
PREFLIGHT = ROOT / "tools" / "security" / "edge1-project-completion-preflight.sh"


class Edge1ProjectCompletionBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.activation = ACTIVATION.read_text(encoding="utf-8")
        cls.preflight = PREFLIGHT.read_text(encoding="utf-8")

    def test_shell_syntax(self) -> None:
        for path in (ACTIVATION, PREFLIGHT):
            result = subprocess.run(
                ["bash", "-n", str(path)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_activation_is_narrow_and_rollback_safe(self) -> None:
        text = self.activation
        for marker in (
            "branch --show-current",
            "status --porcelain",
            "merge-base --is-ancestor",
            "BACKUP_DIR",
            "trap rollback ERR INT TERM",
            "restore_file \"$TARGET_UNIT\" service.unit",
            "restore_file \"$STATUS_FILE\" network-defense.json",
            "systemctl daemon-reload",
            "systemctl start \"$SERVICE\"",
            "network stale threshold is not 600 seconds",
            "verified_enforcement_count changed unexpectedly",
            "DNS policy state must remain not_staged",
            "traffic_controls_changed must remain false",
            "timer enablement changed unexpectedly",
            "timer active state changed unexpectedly",
            "sha256sum",
        ):
            self.assertIn(marker, text)
        self.assertIn("install -o root -g root -m 0644 \"$SOURCE_UNIT\" \"$TARGET_UNIT\"", text)
        self.assertNotIn("systemctl enable", text)
        self.assertNotIn("systemctl disable", text)
        self.assertNotIn("systemctl start \"$TIMER\"", text)
        self.assertNotIn("systemctl stop \"$TIMER\"", text)
        self.assertNotIn("/var/www/edge1-status/index.html", text)
        self.assertNotIn("src/web/operations-center", text)

    def test_preflight_is_read_only_outside_protected_evidence(self) -> None:
        text = self.preflight
        for marker in (
            "apache-vhosts.txt",
            "apache-modules.txt",
            "apache-config-test.txt",
            "apache-directives.txt",
            "public-filesystem-inventory.txt",
            "route-matrix.tsv",
            "route-header-summary.json",
            "suricata-retention-sizing.json",
            "sqlite-capability.json",
            "staged-public-summary",
            "edge1_public_status_exporter.py",
            "sha256-manifest.txt",
            "live_configuration_changed=false",
        ):
            self.assertIn(marker, text)
        self.assertNotRegex(text, r"systemctl\s+(start|stop|restart|reload|enable|disable|mask|unmask)\b")
        self.assertNotRegex(text, r"git\s+-C\s+\"?\$REPO_ROOT\"?\s+(pull|fetch|merge|reset|clean|checkout|switch|stash)\b")
        self.assertNotIn("/etc/systemd/system/", text)
        self.assertNotIn("/var/www/edge1-status/public/status.json", text)

    def test_bundle_forbids_protected_control_changes(self) -> None:
        combined = self.activation + "\n" + self.preflight
        forbidden = (
            r"\bnft\s",
            r"\biptables\s",
            r"\bip6tables\s",
            r"\bufw\s",
            r"firewall-cmd",
            r"unbound-control",
            r"a2enmod",
            r"a2dismod",
            r"a2ensite",
            r"a2dissite",
            r"apachectl\s+(graceful|restart|stop|start)",
            r"systemctl\s+(restart|reload|stop|start)\s+(apache|apache2|httpd|unbound|fail2ban)",
            r"git\s+(reset|clean|push\s+--force)",
            r"rm\s+-rf\s+/var/www",
        )
        for pattern in forbidden:
            self.assertIsNone(re.search(pattern, combined), pattern)

    def test_evidence_is_protected_and_sanitized(self) -> None:
        self.assertIn("-m 0700", self.activation)
        self.assertIn("-m 0700", self.preflight)
        self.assertIn("<redacted>", self.preflight)
        self.assertNotIn("cat /etc/shadow", self.preflight)
        self.assertNotIn("printenv", self.preflight)
        self.assertNotIn("env >", self.preflight)
        self.assertNotIn("authorized_keys", self.preflight)
        self.assertNotIn("id_rsa", self.preflight)

    def test_activation_only_updates_existing_observability_behavior(self) -> None:
        self.assertIn("wwcx-network-defense.service", self.activation)
        self.assertIn("network_defense_freshness_exporter.py", self.activation)
        self.assertIn("NETWORK_DEFENSE_FRESHNESS_REQUIRED_COMMIT", self.activation)
        self.assertIn("711952afb053fa3bd50c390516fa7b58f3943985", self.activation)
        self.assertNotIn("edge1_public_status_exporter.py", self.activation)
        self.assertNotIn("public-status", self.activation)
        self.assertNotIn("apache", self.activation.lower())
        self.assertNotIn("auth", self.activation.lower())


if __name__ == "__main__":
    unittest.main()
