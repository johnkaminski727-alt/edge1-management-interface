#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import socket
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from server.ava_call_archive import manifest_sha256
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
        self.archive = Path(self.tmp.name) / "call-archive"
        (self.archive / "manifests").mkdir(parents=True)
        (self.archive / "transcripts").mkdir()
        transcript = b"Caller: Please call me back about the equipment return.\n"
        (self.archive / "transcripts" / "transcript-0001.txt").write_bytes(transcript)
        manifest = {
            "schema_version": 1,
            "call_ref": "call-0001",
            "started_at_utc": "2026-08-23T09:00:00Z",
            "direction": "inbound",
            "caller_ref": "contact-jane",
            "disposition": "voicemail",
            "transcript_ref": "transcript-0001",
            "segments": [{"kind": "voicemail", "transcript_ref": "transcript-0001"}],
            "integrity": {
                "manifest_sha256": "0" * 64,
                "transcript_sha256": hashlib.sha256(transcript).hexdigest(),
            },
        }
        manifest["integrity"]["manifest_sha256"] = manifest_sha256(manifest)
        (self.archive / "manifests" / "call-0001.json").write_text(json.dumps(manifest), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

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
            build_server("0.0.0.0", 8116, self.db, self.archive)

    def test_call_archive_is_bound_to_loopback_server(self) -> None:
        server = build_server("127.0.0.1", self._free_port(), self.db, self.archive)
        try:
            self.assertEqual(server.RequestHandlerClass.call_archive.root, self.archive)
            self.assertEqual(server.RequestHandlerClass.call_archive.voicemails()[0]["call_ref"], "call-0001")
        finally:
            server.server_close()

    def test_call_and_transcript_endpoints_are_read_only(self) -> None:
        server = build_server("127.0.0.1", self._free_port(), self.db, self.archive)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urllib.request.urlopen(base + "/api/ava-office/voicemails?limit=5", timeout=2) as response:
                payload = json.load(response)
            self.assertEqual(payload["items"][0]["call_ref"], "call-0001")
            self.assertNotIn("text", payload["items"][0])
            with urllib.request.urlopen(base + "/api/ava-office/transcript?call_ref=call-0001", timeout=2) as response:
                transcript = json.load(response)
            self.assertIn("equipment return", transcript["text"])
            self.assertTrue(transcript["sha256_verified"])
            self.assertFalse(transcript["audio_exposed"])
            request = urllib.request.Request(base + "/api/ava-office/calls", data=b"{}", method="POST")
            with self.assertRaises(urllib.error.HTTPError) as blocked:
                urllib.request.urlopen(request, timeout=2)
            self.assertEqual(blocked.exception.code, 405)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


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
