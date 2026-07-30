from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/security/edge1-security-boundary-live-inventory.sh"
RECONCILER = ROOT / "tools/security/reconcile-edge1-live-inventory.py"
REDACTOR = ROOT / "tools/security/redact-edge1-boundary-text.py"
AUTHORIZATION = ROOT / "config/security/edge1-security-completion-authorization-20260730.json"
MANIFEST = ROOT / "config/security/edge1-restricted-artifact-migration-manifest.json"


class LiveInventoryTests(unittest.TestCase):
    def test_authorization_records_exact_programs_and_guardrails(self):
        value = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
        self.assertEqual(value["contract"], "wwcx.edge1-security-completion-authorization.v1")
        self.assertTrue(all(value["programs"].values()))
        self.assertTrue(value["authorized_actions"]["read_only_live_inventory"])
        self.assertTrue(value["authorized_actions"]["bounded_reversible_production_deployment"])
        guard = value["guardrails"]
        for key in (
            "dns_enforcement_change",
            "unbound_or_rpz_change",
            "firewall_or_nftables_change",
            "routing_change",
            "ids_rule_change",
            "reputation_list_change",
            "new_public_listener",
            "credential_material_in_repository",
            "raw_alert_publication",
            "retained_evidence_deletion",
        ):
            self.assertFalse(guard[key])
        self.assertTrue(guard["archive_before_withdrawal"])
        self.assertTrue(guard["authenticated_equivalence_before_cutover"])

    def test_inventory_script_is_read_only_and_secret_minimized(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "read_only_live_inventory",
            "public-filesystem-inventory.json",
            "public-filesystem-anomalies.json",
            "reconcile-edge1-live-inventory.py",
            "apache-boundary-readiness.json",
            "route-header-summary.json",
            "sha256-manifest.txt",
            "redact-edge1-boundary-text.py",
            "source_tree_mutated':False",
            "credentials_collected':False",
            "traffic_controls_changed':False",
            "restricted='/edge1-ops/' if",
        ):
            self.assertIn(marker, text)
        for pattern in (
            r"systemctl\s+(start|stop|restart|reload|enable|disable|mask|unmask)",
            r"\b(a2enmod|a2dismod|a2enconf|a2disconf|a2ensite|a2dissite)\b",
            r"\b(cp|mv|rm|chmod|chown|install)\s+(?!-d\b)",
            r"\b(nft|iptables|ip6tables|ufw|firewall-cmd)\b",
            r"\b(unbound-control|suricata-update)\b",
            r"curl[^\n]*(--user|-u\s)",
            r"(?i)authorization:\s",
            r"(?i)cookie:\s",
            r"git\s+-C\s+\"\$REPO_ROOT\"\s+remote\s+-v",
            r"/etc/shadow|/root/\.ssh|id_rsa|printenv|\benv\s*>",
        ):
            self.assertIsNone(re.search(pattern, text), pattern)
        self.assertIn('systemctl cat "$unit" 2>&1 \\\n        | python3 "$REDACTOR"', text)

    def test_redactor_removes_assignments_urls_and_auth_headers(self):
        sample = (
            "Environment=CLIENT_SECRET=hunter2\n"
            "proxy=https://alice:password@example.invalid/\n"
            "Authorization: Bearer abc.def.ghi\n"
            "Cookie=session=abcdef\n"
        )
        result = subprocess.run(
            [sys.executable, str(REDACTOR)],
            input=sample,
            text=True,
            check=True,
            capture_output=True,
        ).stdout
        for forbidden in ("hunter2", "alice:password", "abc.def.ghi", "abcdef"):
            self.assertNotIn(forbidden, result)
        self.assertIn("<redacted>", result)

    def run_reconciler(self, inventory):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            source = root / "inventory.json"
            output = root / "result.json"
            source.write_text(json.dumps(inventory), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(RECONCILER),
                    "--inventory",
                    str(source),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            return json.loads(output.read_text(encoding="utf-8")), json.loads(completed.stdout)

    def test_reconciler_maps_complete_exact_inventory_without_live_access(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        inventory = [
            {
                "path": "/var/www/edge1-status/" + item["source_relative"],
                "sha256": "a" * 64,
                "mode": "0644",
                "bytes": index + 1,
            }
            for index, item in enumerate(manifest["known_exact_artifacts"])
        ]
        inventory.append({
            "path": "/var/www/edge1-status/operator-maintained-note.txt",
            "sha256": "b" * 64,
            "mode": "0640",
            "bytes": 17,
        })
        value, stdout = self.run_reconciler(inventory)
        self.assertEqual(value, stdout)
        self.assertEqual(value["counts"]["mapped"], len(manifest["known_exact_artifacts"]))
        self.assertEqual(value["counts"]["missing_known"], 0)
        self.assertEqual(value["counts"]["unknown_preserved"], 1)
        self.assertEqual(value["unknown_preserved"][0]["action"], "preserve_review")
        self.assertFalse(value["staging_ready"])
        self.assertFalse(value["cutover_ready"])
        self.assertFalse(value["live_files_opened_by_reconciler"])
        self.assertFalse(value["source_tree_mutated"])
        self.assertFalse(value["credentials_collected"])

    def test_reconciler_accepts_slash_terminated_manifest_prefixes(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        prefix = manifest["known_prefix_groups"][0]["source_prefix"]
        self.assertTrue(prefix.endswith("/"))
        inventory = [{
            "path": "/var/www/edge1-status/" + prefix + "live.json",
            "sha256": "c" * 64,
            "mode": "0644",
            "bytes": 9,
        }]
        value, stdout = self.run_reconciler(inventory)
        self.assertEqual(value, stdout)
        self.assertEqual(value["counts"]["mapped"], 1)
        self.assertEqual(value["mapped"][0]["provenance"], "prefix_live_enumeration")
        self.assertFalse(value["staging_ready"])
        self.assertFalse(value["cutover_ready"])

    def test_reconciler_rejects_unsafe_directory_prefixes(self):
        script = RECONCILER.read_text(encoding="utf-8")
        self.assertIn('segment_value = value[:-1]', script)
        self.assertIn('part in {"", ".", ".."}', script)
        self.assertIn('migration.safe_relative = safe_relative', script)

    def test_reconciler_and_redactor_have_no_network_or_command_execution(self):
        combined = RECONCILER.read_text(encoding="utf-8") + REDACTOR.read_text(encoding="utf-8")
        for forbidden in (
            "subprocess.",
            "socket.",
            "requests.",
            "urllib.request",
            "systemctl",
            "apachectl",
            "/var/www/edge1-status",
            "/etc/shadow",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
