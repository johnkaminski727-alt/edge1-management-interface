#!/usr/bin/env python3
"""Offline fixture tests for the scoped Spamhaus recovery primitive."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "tools/networking/spamhaus_scoped_recovery.py"
SPEC = importlib.util.spec_from_file_location("scoped_spamhaus_recovery", SOURCE)
RECOVERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECOVERY)


class FakeNft:
    def __init__(self, table_present=True, *, query_failed=False, malformed=False, delete_failed=False):
        self.tables = {("inet", "ufw"), ("ip", "crowdsec")}
        if table_present:
            self.tables.add(("inet", "bigbird_spamhaus"))
        self.query_failed = query_failed
        self.malformed = malformed
        self.delete_failed = delete_failed
        self.commands = []

    def __call__(self, args):
        args = list(args)
        self.commands.append(args)
        if args == [RECOVERY.NFT, "-j", "list", "tables"]:
            if self.query_failed:
                return subprocess.CompletedProcess(args, 1, "", "simulated failure")
            if self.malformed:
                return subprocess.CompletedProcess(args, 0, "{not json}", "")
            return subprocess.CompletedProcess(args, 0, json.dumps({
                "nftables": [{"table": {"family": fam, "name": name}} for fam, name in sorted(self.tables)]
            }), "")
        if args == [RECOVERY.NFT, "delete", "table", "inet", "bigbird_spamhaus"]:
            if self.delete_failed:
                return subprocess.CompletedProcess(args, 1, "", "simulated failure")
            self.tables.remove(("inet", "bigbird_spamhaus"))
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError("Unexpected nft command (potentially unsafe): " + repr(args))


class RecoveryTests(unittest.TestCase):
    def test_target_removed_and_other_tables_preserved(self):
        fake = FakeNft()
        self.assertEqual(RECOVERY.recover(fake, execute=True), "removed_verified")
        self.assertEqual(fake.tables, {("inet", "ufw"), ("ip", "crowdsec")})
        self.assertEqual(RECOVERY.recover(fake, execute=True), "already_absent")

    def test_default_only_inspects(self):
        fake = FakeNft()
        self.assertEqual(RECOVERY.recover(fake), "present_check_only")
        self.assertEqual(len(fake.commands), 1)
        self.assertIn(("inet", "bigbird_spamhaus"), fake.tables)

    def test_target_already_absent(self):
        fake = FakeNft(table_present=False)
        self.assertEqual(RECOVERY.recover(fake, execute=True), "already_absent")
        self.assertEqual(len(fake.commands), 1)

    def test_query_failure_fails_closed(self):
        fake = FakeNft(query_failed=True)
        with self.assertRaises(RuntimeError):
            RECOVERY.recover(fake, execute=True)
        self.assertEqual(len(fake.commands), 1)

    def test_malformed_query_fails_closed(self):
        fake = FakeNft(malformed=True)
        with self.assertRaises(RuntimeError):
            RECOVERY.recover(fake, execute=True)
        self.assertEqual(len(fake.commands), 1)

    def test_failed_delete_reported(self):
        fake = FakeNft(delete_failed=True)
        with self.assertRaises(RuntimeError):
            RECOVERY.recover(fake, execute=True)
        self.assertIn(("inet", "bigbird_spamhaus"), fake.tables)
        self.assertIn(("inet", "ufw"), fake.tables)


if __name__ == "__main__":
    unittest.main()
