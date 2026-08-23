#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from server.ava_call_archive import AvaCallArchiveError, AvaCallArchiveReadModel
from server.ava_call_archive_writer import AvaCallArchiveWriteError, AvaCallArchiveWriter, ZERO_SHA256


class AvaCallArchiveWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "archive"
        self.writer = AvaCallArchiveWriter(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def manifest(self, **overrides):
        document = {
            "schema_version": 1,
            "call_ref": "call-0001",
            "started_at_utc": "2026-08-23T10:00:00Z",
            "answered_at_utc": "2026-08-23T10:00:03Z",
            "ended_at_utc": "2026-08-23T10:01:00Z",
            "direction": "inbound",
            "caller_ref": "contact-jane",
            "called_party_ref": "wwcx-main",
            "disposition": "voicemail",
            "recording_policy": {
                "enabled": False,
                "notice_required": True,
                "consent_required": False,
                "consent_state": "not_required",
            },
            "transcription_policy": {"enabled": True, "streaming": True, "speaker_separation": True},
            "recording_ref": None,
            "transcript_ref": "transcript-0001",
            "summary_ref": None,
            "segments": [{
                "segment_ref": "segment-0001",
                "kind": "voicemail",
                "privacy": "protected_evidence",
                "started_at_utc": "2026-08-23T10:00:05Z",
                "ended_at_utc": "2026-08-23T10:01:00Z",
                "audio_ref": None,
                "transcript_ref": "transcript-0001",
            }],
            "events": [{
                "event_ref": "event-0001",
                "type": "notice",
                "occurred_at_utc": "2026-08-23T10:00:04Z",
                "actor_ref": "ava",
            }],
            "integrity": {
                "manifest_sha256": ZERO_SHA256,
                "recording_sha256": None,
                "transcript_sha256": None,
            },
        }
        document.update(overrides)
        return document

    def append_transcript(self) -> None:
        self.writer.append_transcript_event(
            call_ref="call-0001",
            event_ref="utterance-0001",
            occurred_at_utc="2026-08-23T10:00:10Z",
            speaker="caller",
            text="Please call me back.",
        )
        self.writer.append_transcript_event(
            call_ref="call-0001",
            event_ref="utterance-0002",
            occurred_at_utc="2026-08-23T10:00:12Z",
            speaker="ava",
            text="I will pass that along.",
        )

    def test_finalize_is_immutable_and_reader_verifies_hashes(self) -> None:
        self.append_transcript()
        result = self.writer.finalize_call(self.manifest())
        self.assertTrue(result["immutable"])
        self.assertTrue(result["journal_preserved"])
        self.assertFalse(result["audio_copied"])
        reader = AvaCallArchiveReadModel(self.root)
        document = reader.manifest("call-0001")
        self.assertEqual(document["integrity"]["manifest_sha256"], result["manifest_sha256"])
        self.assertIn("Please call me back", reader.transcript("call-0001")["text"])
        with self.assertRaises(AvaCallArchiveWriteError):
            self.writer.finalize_call(self.manifest())

    def test_manifest_tamper_is_rejected(self) -> None:
        self.append_transcript()
        self.writer.finalize_call(self.manifest())
        path = self.root / "manifests" / "call-0001.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["disposition"] = "answered"
        path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(AvaCallArchiveError):
            AvaCallArchiveReadModel(self.root).manifest("call-0001")

    def test_transcript_tamper_is_rejected(self) -> None:
        self.append_transcript()
        self.writer.finalize_call(self.manifest())
        (self.root / "transcripts" / "transcript-0001.txt").write_text("tampered", encoding="utf-8")
        with self.assertRaises(AvaCallArchiveError):
            AvaCallArchiveReadModel(self.root).transcript("call-0001")

    def test_required_notice_and_consent_fail_closed(self) -> None:
        self.append_transcript()
        with self.assertRaisesRegex(AvaCallArchiveWriteError, "notice"):
            self.writer.finalize_call(self.manifest(events=[]))
        consent = self.manifest(recording_policy={
            "enabled": False,
            "notice_required": True,
            "consent_required": True,
            "consent_state": "declined",
        })
        with self.assertRaisesRegex(AvaCallArchiveWriteError, "consent"):
            self.writer.finalize_call(consent)

    def test_recording_reference_requires_policy_and_hash(self) -> None:
        self.append_transcript()
        with self.assertRaises(AvaCallArchiveWriteError):
            self.writer.finalize_call(self.manifest(recording_ref="recording-0001"))
        document = self.manifest(
            recording_policy={
                "enabled": True,
                "notice_required": True,
                "consent_required": False,
                "consent_state": "not_required",
            },
            recording_ref="recording-0001",
        )
        with self.assertRaisesRegex(AvaCallArchiveWriteError, "recording_sha256"):
            self.writer.finalize_call(document)

    def test_paths_and_duplicate_events_are_rejected(self) -> None:
        with self.assertRaises(AvaCallArchiveWriteError):
            self.writer.append_transcript_event(
                call_ref="../escape",
                event_ref="event-0001",
                occurred_at_utc="2026-08-23T10:00:10Z",
                speaker="caller",
                text="x",
            )
        for occurred, text in (("2026-08-23T10:00:10Z", "x"), ("2026-08-23T10:00:11Z", "y")):
            self.writer.append_transcript_event(
                call_ref="call-0001",
                event_ref="event-0001",
                occurred_at_utc=occurred,
                speaker="caller",
                text=text,
            )
        with self.assertRaisesRegex(AvaCallArchiveWriteError, "duplicate"):
            self.writer.finalize_call(self.manifest())


if __name__ == "__main__":
    unittest.main()
