#!/usr/bin/env python3
"""G2 local candidate persistence tests; temp directories only."""
import copy
import importlib.util
import sys
import tempfile
from pathlib import Path
import unittest

TOOL = Path(__file__).resolve().parents[1] / "tools/operations"
sys.path.insert(0, str(TOOL))
from edge1_candidate_store import CandidateStore, ConflictError, CandidateError


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "candidate.sqlite"
        self.store = CandidateStore(self.path)

    def test_defaults_and_restart_persistence(self):
        first = self.store.read()
        self.assertFalse(first["pending"])
        self.assertFalse(first["execution_allowed"])
        p = self.store.propose("dashboard", "refresh_seconds", 90,
                               expected_candidate_revision=first["candidate_revision"])
        self.assertTrue(p["pending"])
        self.assertEqual(p["candidate"]["dashboard"]["refresh_seconds"], 90)
        self.assertEqual(p["running"]["dashboard"]["refresh_seconds"], 30)
        self.assertEqual(CandidateStore(self.path).read()["candidate"]["dashboard"]["refresh_seconds"], 90)
        self.assertEqual(len(self.store.audit()), 1)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_concurrent_tabs_rejected(self):
        base = self.store.read()["candidate_revision"]
        first = self.store.propose("alerts", "max_items", 12,
                                   expected_candidate_revision=base)
        with self.assertRaises(ConflictError):
            CandidateStore(self.path).propose("alerts", "max_items", 22,
                                              expected_candidate_revision=base)
        self.assertEqual(len(self.store.audit()), 1)
        self.assertEqual(first["candidate"]["alerts"]["max_items"], 12)

    def test_discard_is_persistent(self):
        old = self.store.read()["candidate_revision"]
        p = self.store.propose("inventory", "show_vpn_peers", True,
                               expected_candidate_revision=old)
        reset = CandidateStore(self.path).discard(expected_candidate_revision=p["candidate_revision"])
        self.assertFalse(reset["pending"])
        self.assertEqual(len(self.store.audit()), 2)

    def test_unknown_settings_never_persist_or_audit(self):
        original = self.store.read()
        for section, field, value in [
            ("network", "dns", "1.1.1.1"),
            ("alerts", "password", "secret"),
            ("inventory", "show_vpn_peers", "true"),
            ("alerts", "max_items", 200),
        ]:
            with self.subTest(section=section, field=field):
                with self.assertRaises(CandidateError):
                    self.store.propose(section, field, value,
                                       expected_candidate_revision=original["candidate_revision"])
                self.assertEqual(self.store.read(), original)
                self.assertEqual(self.store.audit(), [])

    def test_symlink_database_refused(self):
        other = Path(self.temp.name) / "other"
        other.write_bytes(b"not a DB")
        link = Path(self.temp.name) / "linked.sqlite"
        link.symlink_to(other)
        with self.assertRaises(CandidateError):
            CandidateStore(link)

    def test_stored_revision_tamper_refused(self):
        import sqlite3
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE workspace SET candidate_revision=? WHERE id=1", ("0"*64,))
        with self.assertRaises(CandidateError):
            self.store.read()


if __name__ == "__main__":
    unittest.main()
