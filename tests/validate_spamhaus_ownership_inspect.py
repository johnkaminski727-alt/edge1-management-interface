#!/usr/bin/env python3
"""Strict read-only ownership classification regression tests (A245)."""
import importlib.util
import json
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "tools/networking/spamhaus_ownership_inspect.py"
spec = importlib.util.spec_from_file_location("ownership_inspect", path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

RID = "0123456789abcdef0123456789abcdef"


def document(*entries):
    return json.dumps({"nftables": list(entries)})


def owned(comment, *, family="inet", name="bigbird_spamhaus"):
    return {"table": {"family": family, "name": name, "comment": comment}}


class OwnershipInspectionTests(unittest.TestCase):
    def test_missing_target(self):
        self.assertEqual(m.assess_table_ownership(document(
            owned("other", name="ufw")), RID), "absent")

    def test_exact_comment(self):
        self.assertEqual(m.assess_table_ownership(document(
            owned("edge1-spamhaus-run:" + RID)), RID), "owned")

    def test_foreign_or_missing_comment(self):
        for entry in (
            owned("edge1-spamhaus-run:" + "f" * 32),
            owned("arbitrary"),
            {"table": {"family": "inet", "name": "bigbird_spamhaus"}},
        ):
            with self.subTest(entry=entry):
                self.assertEqual(m.assess_table_ownership(document(entry), RID), "foreign")

    def test_duplicate_target_blocks(self):
        entry = owned("edge1-spamhaus-run:" + RID)
        self.assertEqual(m.assess_table_ownership(document(entry, entry), RID), "invalid")

    def test_malformed_fail_closed(self):
        for bad in ("", "{}", '{"nftables": null}', '{"nftables": [null]}',
                    '{"nftables": [{"table": {"name": "bigbird_spamhaus"}}]}'):
            with self.subTest(bad=bad):
                self.assertEqual(m.assess_table_ownership(bad, RID), "invalid")

    def test_forged_or_malformed_run_id_rejected(self):
        for rid in ("", RID.upper(), RID + "x", "f" * 31, "z" * 32):
            with self.assertRaises(ValueError):
                m.assess_table_ownership(document(), rid)

    def test_never_provides_delete_authorization(self):
        self.assertEqual(m.assess_table_ownership(document(
            owned("edge1-spamhaus-run:" + RID)), RID), "owned")
        # This module deliberately contains no nft, subprocess, or delete call.
        src = path.read_text()
        self.assertNotIn("subprocess.run(", src)
        self.assertNotIn("delete table inet bigbird_spamhaus", src)


if __name__ == "__main__":
    unittest.main()
