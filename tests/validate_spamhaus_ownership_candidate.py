#!/usr/bin/env python3
"""Offline, no-firewall tests for Assignment 244 tagged candidate rendering."""
import importlib.util
import pathlib
import unittest

path = pathlib.Path(__file__).resolve().parents[1] / "tools/networking/spamhaus_ownership_candidate.py"
spec = importlib.util.spec_from_file_location("ownership_candidate", path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

RUN = "0123456789abcdef0123456789abcdef"
CANONICAL = (
    "table inet bigbird_spamhaus {\n"
    "  set drop4 { type ipv4_addr; flags interval; elements = { 192.0.2.0/24 }; }\n"
    "  set drop6 { type ipv6_addr; flags interval; elements = { 2001:db8::/32 }; }\n"
    "}\n"
)

class OwnershipCandidateTests(unittest.TestCase):
    def test_preserves_original_and_inserts_only_guard_comment(self):
        derived = m.derive_owned_candidate(CANONICAL, RUN)
        expected = ('create table inet bigbird_spamhaus { comment "edge1-spamhaus-run:'
                    + RUN + '" }\n\n' + CANONICAL)
        self.assertEqual(derived, expected)
        self.assertEqual(CANONICAL.count("comment"), 0)

    def test_unique_run_id(self):
        self.assertRegex(m.new_run_id(), r"^[0-9a-f]{32}$")

    def test_refuses_noncanonical_or_replace_candidate(self):
        for candidate in (
            "delete table inet bigbird_spamhaus\n" + CANONICAL,
            CANONICAL + CANONICAL,
            CANONICAL.replace("table inet", "table ip", 1),
            CANONICAL[:-2],
            CANONICAL.replace("  set drop4", '  comment "edge1-spamhaus-run:evil"\n  set drop4'),
        ):
            with self.subTest(candidate=candidate[:30]):
                with self.assertRaises(ValueError):
                    m.derive_owned_candidate(candidate, RUN)

    def test_rejects_untrusted_run_identifier(self):
        for value in ("bad", RUN.upper(), RUN + '" delete table inet ufw', ""):
            with self.assertRaises(ValueError):
                m.derive_owned_candidate(CANONICAL, value)

    def test_owner_matching_is_strict(self):
        self.assertEqual(m.parse_owner_comment(m.OWNER_PREFIX + RUN), RUN)
        for value in (None, "not-owned", m.OWNER_PREFIX + "malformed",
                      m.OWNER_PREFIX + RUN + "-replay", 1):
            self.assertIsNone(m.parse_owner_comment(value))

if __name__ == "__main__":
    unittest.main()
