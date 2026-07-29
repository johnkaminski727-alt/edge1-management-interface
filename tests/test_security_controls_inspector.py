#!/usr/bin/env python3
"""Validation for sanitized firewall and Fail2ban posture inspection."""

import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "security" / "security_controls_inspector.py"
WRAPPER_PATH = ROOT / "tools" / "security" / "inspect-security-controls.sh"
SPEC = importlib.util.spec_from_file_location("security_controls_inspector", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load security_controls_inspector")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SecurityControlsInspectorTests(unittest.TestCase):
    def test_nft_parser_retains_counts_only(self):
        document = {
            "nftables": [
                {"metainfo": {"version": "1"}},
                {"table": {"family": "inet", "name": "filter"}},
                {"chain": {"family": "inet", "table": "filter", "name": "input"}},
                {"rule": {"family": "inet", "table": "filter", "chain": "input", "expr": [{"match": {"left": {"payload": {"protocol": "ip", "field": "saddr"}}, "right": "192.0.2.4"}}]}},
                {"set": {"family": "inet", "table": "filter", "name": "blocked"}},
                {"counter": {"family": "inet", "table": "filter", "name": "drops"}},
            ]
        }
        result = MODULE.parse_nft_ruleset(document)
        self.assertEqual(result["table_count"], 1)
        self.assertEqual(result["chain_count"], 1)
        self.assertEqual(result["rule_count"], 1)
        self.assertEqual(result["set_count"], 1)
        self.assertEqual(result["named_counter_count"], 1)
        self.assertNotIn("192.0.2.4", json.dumps(result))

    def test_fail2ban_parser_excludes_banned_ip_list(self):
        overview = """Status
|- Number of jail: 2
`- Jail list: sshd, recidive
"""
        jail = """Status for the jail: sshd
|- Filter
|  |- Currently failed: 3
|  `- Total failed: 120
`- Actions
   |- Currently banned: 2
   |- Total banned: 15
   `- Banned IP list: 192.0.2.10 198.51.100.7
"""
        self.assertEqual(MODULE.parse_fail2ban_jail_list(overview), ["recidive", "sshd"])
        metrics = MODULE.parse_fail2ban_jail_status(jail)
        self.assertEqual(metrics["currently_failed"], 3)
        self.assertEqual(metrics["total_failed"], 120)
        self.assertEqual(metrics["currently_banned"], 2)
        self.assertEqual(metrics["total_banned"], 15)
        self.assertNotIn("192.0.2.10", json.dumps(metrics))

    def test_snapshot_writer_is_atomic_and_world_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "security-controls.json"
            MODULE.write_snapshot({"read_only": True}, output)
            self.assertTrue(output.exists())
            self.assertFalse(output.with_suffix(".json.tmp").exists())
            self.assertEqual(output.stat().st_mode & 0o777, 0o644)

    def test_inspector_uses_fixed_read_only_commands(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("shell=True", source)
        self.assertIn('"systemctl",\n        "show"', source)
        self.assertIn('(nft_path, "-j", "list", "ruleset")', source)
        self.assertIn('(client_path, "status")', source)
        forbidden = (
            r"systemctl[^\n]*(?:start|stop|restart|reload|enable|disable)",
            r"nft_path[^\n]*(?:add|delete|insert|replace|flush)",
            r"client_path[^\n]*\"set\"",
        )
        for pattern in forbidden:
            self.assertIsNone(re.search(pattern, source, re.I), pattern)

    def test_wrapper_enforces_privacy_and_no_control_changes(self):
        source = WRAPPER_PATH.read_text(encoding="utf-8")
        for token in (
            "raw_rules_included",
            "addresses_included",
            "ports_included",
            "banned_ip_list_included",
            "raw_command_output_included",
            'traffic_controls_changed=false',
            "No firewall, DNS, routing, IDS, proxy, Fail2ban, or service controls were changed.",
        ):
            self.assertIn(token, source)
        self.assertIsNone(re.search(r"systemctl\s+(?:start|stop|restart|reload|enable|disable)", source, re.I))


if __name__ == "__main__":
    unittest.main()
