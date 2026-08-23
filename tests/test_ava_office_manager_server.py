#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from server.ava_office_manager import OfficeManagerStore
from server.ava_office_manager_server import AvaOfficeReadError, AvaOfficeReadModel, build_server


class AvaOfficeReadModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "office.sqlite3"
        store = OfficeManagerStore(self.db)
        item = store.create_work_item(
            title="Arrange appointment",
            desired_outcome="Schedule a routine appointment.",
            source_channel="chat",
        )
        store.transition_work_item(item["id"], "working")
        store.add_standing_instruction(
            domain="calendar.event.cancel",
            statement="Ask before cancelling appointments.",
            effect="require_confirmation",
        )
        store.propose_action(
            capability="travel.book",
            summary="Book selected itinerary",
            parameters={"itinerary_ref": "option-1234"},
            work_item_id=item["id"],
        )
        self.model = AvaOfficeReadModel(self.db)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_summary_and_bounded_views(self) -> None:
        health = self.model.health()
        self.assertEqual(health["mode"], "read-only")
        summary = self.model.summary()
        self.assertEqual(summary["work_items"]["working"], 1)
        self.assertEqual(summary["actions"]["awaiting_confirmation"], 1)
        self.assertEqual(summary["standing_instructions"], 1)
        self.assertEqual(len(self.model.work_items(limit=10)), 1)
        decisions = self.model.decisions(limit=10)
        self.assertEqual(decisions[0]["status"], "awaiting_confirmation")
        self.assertNotIn("parameters", decisions[0])
        self.assertNotIn("parameters_json", decisions[0])
        self.assertEqual(len(self.model.instructions(limit=10)), 1)

    def test_missing_database_fails_without_creating_it(self) -> None:
        missing = Path(self.tmp.name) / "missing.sqlite3"
        model = AvaOfficeReadModel(missing)
        with self.assertRaises(AvaOfficeReadError):
            model.health()
        self.assertFalse(missing.exists())

    def test_wildcard_listener_is_rejected(self) -> None:
        with self.assertRaises(AvaOfficeReadError):
            build_server("0.0.0.0", 8116, self.db)


class AvaOfficeUiTests(unittest.TestCase):
    def test_mobile_dashboard_exposes_expected_views_and_no_live_mutation_buttons(self) -> None:
        root = Path(__file__).parents[1]
        html = (root / "src" / "web" / "ava-office" / "index.html").read_text(encoding="utf-8")
        js = (root / "src" / "web" / "ava-office" / "app.js").read_text(encoding="utf-8")
        css = (root / "src" / "web" / "ava-office" / "styles.css").read_text(encoding="utf-8")
        for marker in ("Work queue", "Needs You", "Calls &amp; voicemail", "Appointments", "Instructions", "Ask Ava"):
            self.assertIn(marker, html)
        self.assertIn("read-only dashboard cannot approve or execute", html)
        self.assertIn("disabled>Accept", html)
        self.assertIn("credentials: 'same-origin'", js)
        self.assertNotIn("method: 'POST'", js)
        self.assertNotIn("method: 'PUT'", js)
        self.assertIn("@media (max-width: 720px)", css)
        self.assertIn("env(safe-area-inset-bottom)", css)


if __name__ == "__main__":
    unittest.main()
