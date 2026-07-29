#!/usr/bin/env python3
"""Tests for staged DNS Defense RPZ policy compilation."""

import importlib.util
import json
import stat
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "tools" / "networking" / "compile-dns-defense-policy.py"
SPEC = importlib.util.spec_from_file_location("dns_defense_policy", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DnsDefensePolicyTests(unittest.TestCase):
    def policy(self):
        return {
            "schema_version": "1.0",
            "policy_name": "wwcx-dns-defense.rpz",
            "serial": 2026072901,
            "ttl": 60,
            "entries": [
                {"domain": "bad.example", "action": "nxdomain", "include_subdomains": True},
                {"domain": "empty.example", "action": "nodata", "include_subdomains": False},
                {"domain": "good.example", "action": "passthru", "include_subdomains": True},
            ],
        }

    def test_supported_actions_compile(self):
        normalized = MODULE.validate_policy(self.policy())
        zone = MODULE.compile_zone(normalized)
        self.assertIn("bad.example. CNAME .", zone)
        self.assertIn("empty.example. CNAME *.", zone)
        self.assertIn("good.example. CNAME rpz-passthru.", zone)

    def test_staged_include_is_disabled(self):
        normalized = MODULE.validate_policy(self.policy())
        include = MODULE.compile_staged_include(normalized, Path("policy.zone"))
        self.assertIn("rpz-action-override: disabled", include)
        self.assertIn("rpz-log: yes", include)

    def test_status_never_claims_enforcement(self):
        normalized = MODULE.validate_policy(self.policy())
        status = MODULE.build_status(normalized, "zone", "include", Path("policy.json"))
        self.assertTrue(status["read_only"])
        self.assertFalse(status["traffic_controls_changed"])
        self.assertFalse(status["enforcement_enabled"])

    def test_invalid_entries_rejected(self):
        policy = self.policy()
        policy["entries"].append({"domain": "*.bad.example", "action": "nxdomain"})
        with self.assertRaises(MODULE.PolicyError):
            MODULE.validate_policy(policy)

    def test_outputs_are_atomic_and_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "policy.json"
            source.write_text(json.dumps(self.policy()), encoding="utf-8")
            outputs = MODULE.write_outputs(source, root / "out")
            for path in outputs.values():
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)

    def test_no_execution_or_network_dependency(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        for token in ("subprocess", "requests", "urllib.request", "os.system", "socket"):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
