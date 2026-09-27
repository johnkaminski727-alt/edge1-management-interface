#!/usr/bin/env python3
"""G1 in-memory candidate workspace regression tests. Never touch production."""
import copy
import importlib.util
from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[1] / "tools/operations/edge1_candidate_workspace.py"
spec = importlib.util.spec_from_file_location("workspace", SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CandidateWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.running = m.initial_settings()
        self.w = m.Workspace(self.running)
        self.base = self.w.base_revision

    def test_read_only_default(self):
        p = self.w.preview()
        self.assertFalse(p["pending"])
        self.assertFalse(p["execution_allowed"])
        self.assertEqual(p["changes"], [])
        self.assertEqual(p["diff"], "")
        self.assertEqual(self.w.running, self.running)

    def test_proposal_is_candidate_only(self):
        p = self.w.propose("dashboard", "refresh_seconds", 60, expected_revision=self.base)
        self.assertTrue(p["pending"])
        self.assertEqual(p["changes"][0]["path"], "dashboard.refresh_seconds")
        self.assertIn("-    \"refresh_seconds\": 30", p["diff"])
        self.assertIn("+    \"refresh_seconds\": 60", p["diff"])
        self.assertEqual(self.w.running, self.running)
        self.assertFalse(p["execution_allowed"])
        self.assertEqual(self.w.audit[0]["execution"], "none")

    def test_discard_and_copies_do_not_leak(self):
        self.w.propose("inventory", "show_vpn_peers", True, expected_revision=self.base)
        exported = self.w.candidate
        exported["inventory"]["show_vpn_peers"] = False
        self.assertTrue(self.w.candidate["inventory"]["show_vpn_peers"])
        self.w.discard(expected_revision=self.base)
        self.assertFalse(self.w.pending)
        self.assertEqual(self.w.running, self.w.candidate)

    def test_invalid_changes_are_atomic(self):
        before = self.w.preview()
        for section, field, value in [
            ("dashboard", "refresh_seconds", True),
            ("dashboard", "refresh_seconds", 1),
            ("dashboard", "panels", ["system", "system"]),
            ("dashboard", "panels", ["secret"]),
            ("alerts", "max_items", 0),
            ("alerts", "max_items", False),
            ("inventory", "show_routes", "false"),
            ("network", "nameserver", "127.0.0.1"),
            ("dashboard", "password", "do not store"),
        ]:
            with self.subTest(section=section, field=field, value=value):
                with self.assertRaises(m.CandidateError):
                    self.w.propose(section, field, value, expected_revision=self.base)
                self.assertEqual(self.w.preview(), before)
        self.assertEqual(self.w.audit, [])

    def test_stale_revision_refused(self):
        with self.assertRaises(m.CandidateError):
            self.w.propose("alerts", "max_items", 4, expected_revision="0" * 64)
        with self.assertRaises(m.CandidateError):
            self.w.discard(expected_revision="1" * 64)

    def test_drift_protects_pending_changes(self):
        self.w.propose("alerts", "max_items", 4, expected_revision=self.base)
        updated = copy.deepcopy(self.running)
        updated["alerts"]["show_warnings"] = False
        with self.assertRaisesRegex(m.CandidateError, "resolve drift"):
            self.w.rebase_running(updated)
        self.assertTrue(self.w.pending)
        self.assertEqual(self.w.running, self.running)

    def test_rebase_without_pending_changes(self):
        update = copy.deepcopy(self.running)
        update["alerts"]["max_items"] = 10
        self.w.rebase_running(update)
        self.assertEqual(self.w.running["alerts"]["max_items"], 10)
        self.assertFalse(self.w.pending)
        self.assertNotEqual(self.w.base_revision, self.base)

    def test_sorted_panels_and_no_external_effects(self):
        incoming = copy.deepcopy(self.running)
        incoming["dashboard"]["panels"] = ["network", "system"]
        w = m.Workspace(incoming)
        self.assertEqual(w.running["dashboard"]["panels"], ["network", "system"])
        # Pure canonicalization does not mutate caller-provided object.
        self.assertEqual(incoming["dashboard"]["panels"], ["network", "system"])
        content = SRC.read_text(encoding="utf-8")
        for unsafe in ("import subprocess", "import requests", "systemctl", "nft delete", "socket.connect"):
            self.assertNotIn(unsafe, content)


if __name__ == "__main__":
    unittest.main()
