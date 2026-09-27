#!/usr/bin/env python3
"""Assignment 247 offline concurrency and fail-closed ownership tests."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "tools/networking/spamhaus_run_scoped_candidate.py"
spec = importlib.util.spec_from_file_location("run_scoped", path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

A = "0123456789abcdef0123456789abcdef"
B = "abcdef0123456789abcdef0123456789"
CANONICAL = (
    "table inet bigbird_spamhaus {\n"
    "  set drop4 {\n"
    "    type ipv4_addr\n"
    "    flags interval\n"
    "    elements = { 192.0.2.0/24 }\n"
    "  }\n"
    "  set drop6 {\n"
    "    type ipv6_addr\n"
    "    flags interval\n"
    "    elements = { 2001:db8::/32 }\n"
    "  }\n"
    "  chain input { type filter hook input priority -110; policy accept; ip saddr @drop4 counter drop }\n"
    "  chain forward { type filter hook forward priority -110; policy accept; ip6 saddr @drop6 counter drop }\n"
    "}\n"
)


class RunScopedTests(unittest.TestCase):
    def test_unique_table_per_attempt(self):
        first = m.render_scoped_candidate(CANONICAL, A)
        second = m.render_scoped_candidate(CANONICAL, B)
        self.assertNotEqual(m.table_name(A), m.table_name(B))
        self.assertNotIn(m.table_name(B), first)
        self.assertNotIn(m.table_name(A), second)
        self.assertNotIn("table inet bigbird_spamhaus {", first)
        self.assertTrue(first.startswith("create table inet " + m.table_name(A) + " {\n"))
        self.assertIn('comment "' + m.expected_owner_comment(A) + '";', first)
        self.assertEqual(first.count(m.table_name(A)), 2)
        self.assertEqual(first.replace(m.table_name(A), m.CANONICAL).split("}\n\n", 1)[1], CANONICAL)

    def test_classifies_only_this_attempt(self):
        first = {"table": {"family": "inet", "name": m.table_name(A), "comment": m.expected_owner_comment(A)}}
        second = {"table": {"family": "inet", "name": m.table_name(B), "comment": m.expected_owner_comment(B)}}
        ordinary = {"table": {"family": "inet", "name": m.CANONICAL}}
        doc = {"nftables": [first, second, ordinary]}
        self.assertEqual(m.classify_scoped_table(doc, A), "owned")
        self.assertEqual(m.classify_scoped_table(doc, B), "owned")
        self.assertEqual(m.classify_scoped_table({"nftables": [second, ordinary]}, A), "absent")

    def test_foreign_replacement_never_classifies_owned(self):
        for comment in (m.expected_owner_comment(B), "untrusted", None):
            doc = {"nftables": [{"table": {"family": "inet", "name": m.table_name(A), "comment": comment}}]}
            self.assertEqual(m.classify_scoped_table(doc, A), "foreign")
        dup = {"table": {"family": "inet", "name": m.table_name(A), "comment": m.expected_owner_comment(A)}}
        self.assertEqual(m.classify_scoped_table({"nftables": [dup, dup]}, A), "invalid")

    def test_rejects_invalid_input(self):
        for rid in ("", "ABCDEF0123456789ABCDEF0123456789", "z" * 32, A + "; delete", None):
            with self.subTest(rid=rid):
                with self.assertRaises(ValueError):
                    m.table_name(rid)
        for candidate in (
            CANONICAL + CANONICAL,
            "delete table inet bigbird_spamhaus\n" + CANONICAL,
            CANONICAL.replace("table inet bigbird_spamhaus", "table ip bigbird_spamhaus", 1),
            CANONICAL[:-2],
            CANONICAL.replace("  set drop4", "  include /etc/nftables.conf\n  set drop4", 1),
        ):
            with self.subTest(candidate=candidate[:32]):
                with self.assertRaises(ValueError):
                    m.render_scoped_candidate(candidate, A)

    def test_no_recovery_or_apply_code(self):
        content = path.read_text()
        self.assertNotIn("subprocess.run(", content)
        self.assertNotIn("delete table inet", content)
        self.assertNotIn("systemd-run", content)


if __name__ == "__main__":
    unittest.main()
