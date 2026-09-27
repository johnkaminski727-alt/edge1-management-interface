#!/usr/bin/env python3
"""Assignment 250: offline fail-closed rollback classification tests."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "tools/networking/spamhaus_rollback_decision.py"
spec = importlib.util.spec_from_file_location("spamhaus_rollback_decision", path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

A = "0123456789abcdef0123456789abcdef"
B = "abcdef0123456789abcdef0123456789"
META = {
    "run_id": A,
    "table_name": "bigbird_spamhaus_run_" + A,
    "boot_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "candidate_sha256": "1" * 64,
    "timer_unit": "edge1-spamhaus-run-" + A + ".timer",
}

def doc(*entries):
    return {"nftables": list(entries)}

def row(name, comment=None):
    r = {"family": "inet", "name": name}
    if comment is not None:
        r["comment"] = comment
    return {"table": r}

OWNED = row(META["table_name"], "edge1-spamhaus-run:" + A)
OTHER = row("bigbird_spamhaus_run_" + B, "edge1-spamhaus-run:" + B)
CANONICAL = row("bigbird_spamhaus")


class RollbackDecisionTests(unittest.TestCase):
    def check(self, meta, nft, reason, **kwargs):
        result = m.evaluate_rollback(meta, nft, **kwargs)
        self.assertEqual(result["reason"], reason)
        self.assertEqual(result["decision"], "do_not_delete")
        self.assertIs(result["command_allowed"], False)
        self.assertIs(result["watchdog_disarm_allowed"], False)
        self.assertTrue(m.verify_evidence_digest(result))
        return result

    def test_owned_is_not_delete_permission(self):
        result = self.check(META, doc(OWNED, OTHER, CANONICAL), "observed_owned")
        self.assertTrue(result["requires_human_review"])
        self.assertEqual(result["metadata"], META)

    def test_foreign_replacement_and_missing_comment(self):
        for foreign in (
            row(META["table_name"], "edge1-spamhaus-run:" + B),
            row(META["table_name"], "untrusted"),
            row(META["table_name"]),
        ):
            with self.subTest(foreign=foreign):
                self.check(META, doc(foreign), "foreign")

    def test_absent_does_not_touch_other_tables(self):
        result = self.check(META, doc(OTHER, CANONICAL), "absent")
        self.assertFalse(result["requires_human_review"])
        self.check(META, doc(), "absent")

    def test_malformed_duplicates_and_inspection_failure(self):
        for nft in (None, {}, {"nftables": {}}, {"nftables": [None]},
                    {"nftables": [{"table": {"family": "inet"}}]},
                    doc(OWNED, OWNED)):
            with self.subTest(nft=nft):
                self.check(META, nft, "invalid_listing")
        self.check(META, doc(OWNED), "inspection_failed", inspection_error=True)
        self.check(META, doc(OWNED), "invalid_input", inspection_error="false")

    def test_invalid_metadata_fails_closed(self):
        bad = [None, {}, {"run_id": A}, dict(META, run_id=B),
               dict(META, candidate_sha256="g" * 64),
               dict(META, boot_id="malformed"),
               dict(META, timer_unit="wrong.timer"),
               dict(META, extra="unexpected")]
        for item in bad:
            with self.subTest(item=item):
                result = self.check(item, doc(OWNED), "invalid_metadata")
                self.assertIsNone(result["metadata"])

    def test_altered_decision_digest_is_detected(self):
        result = self.check(META, doc(OWNED), "observed_owned")
        altered = dict(result, reason="absent")
        self.assertFalse(m.verify_evidence_digest(altered))
        altered = dict(result, command_allowed=True)
        self.assertFalse(m.verify_evidence_digest(altered))

    def test_no_firewall_or_timer_execution_capabilities(self):
        code = path.read_text(encoding="utf-8")
        for forbidden in ("import subprocess", "import os", "nft delete",
                          "systemctl stop", "systemd-run", "subprocess.run"):
            self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
