#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from server.ava_call_archive import AvaCallArchiveError, AvaCallArchiveReadModel, manifest_sha256


class AvaCallArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "manifests").mkdir()
        (self.root / "transcripts").mkdir()
        self.text = b"Caller: Please call me back about the equipment return.\n"
        (self.root / "transcripts" / "transcript-0001.txt").write_bytes(self.text)
        manifest = {
            "schema_version": 1,
            "call_ref": "call-0001",
            "started_at_utc": "2026-08-23T09:00:00Z",
            "answered_at_utc": "2026-08-23T09:00:05Z",
            "ended_at_utc": "2026-08-23T09:01:00Z",
            "direction": "inbound",
            "caller_ref": "contact-jane",
            "called_party_ref": "wwcx-main",
            "disposition": "voicemail",
            "recording_policy": {"enabled": True, "notice_required": True, "consent_required": False, "consent_state": "not_required"},
            "transcription_policy": {"enabled": True, "streaming": True, "speaker_separation": True},
            "recording_ref": "recording-0001",
            "transcript_ref": "transcript-0001",
            "summary_ref": None,
            "segments": [{"segment_ref": "segment-0001", "kind": "voicemail", "privacy": "protected_evidence", "started_at_utc": "2026-08-23T09:00:10Z", "ended_at_utc": "2026-08-23T09:01:00Z", "audio_ref": "audio-0001", "transcript_ref": "transcript-0001"}],
            "events": [],
            "integrity": {"manifest_sha256": "0" * 64, "recording_sha256": None, "transcript_sha256": hashlib.sha256(self.text).hexdigest()},
        }
        manifest["integrity"]["manifest_sha256"] = manifest_sha256(manifest)
        self.manifest_path = self.root / "manifests" / "call-0001.json"
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.model = AvaCallArchiveReadModel(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_lists_calls_without_audio_or_transcript_body(self) -> None:
        item = self.model.calls()[0]
        self.assertEqual(item["caller_ref"], "contact-jane")
        self.assertTrue(item["voicemail"])
        self.assertTrue(item["transcript_available"])
        self.assertNotIn("text", item)
        self.assertNotIn("audio_ref", item)

    def test_lists_voicemails(self) -> None:
        self.assertEqual([item["call_ref"] for item in self.model.voicemails()], ["call-0001"])

    def test_reads_verified_transcript_but_never_audio(self) -> None:
        result = self.model.transcript("call-0001")
        self.assertIn("equipment return", result["text"])
        self.assertTrue(result["sha256_verified"])
        self.assertFalse(result["audio_exposed"])
        self.assertEqual(result["privacy"], "protected_evidence")

    def test_transcript_integrity_mismatch_fails_closed(self) -> None:
        (self.root / "transcripts" / "transcript-0001.txt").write_text("tampered", encoding="utf-8")
        with self.assertRaises(AvaCallArchiveError):
            self.model.transcript("call-0001")

    def test_manifest_integrity_mismatch_fails_closed(self) -> None:
        document = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        document["disposition"] = "answered"
        self.manifest_path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(AvaCallArchiveError):
            self.model.manifest("call-0001")

    def test_reference_traversal_is_rejected(self) -> None:
        with self.assertRaises(AvaCallArchiveError):
            self.model.transcript("../call-0001")

    def test_archive_health_is_read_only(self) -> None:
        self.assertEqual(self.model.health(), {"status": "ok", "mode": "read-only", "archive_available": True, "manifest_count": 1})


if __name__ == "__main__":
    unittest.main()
