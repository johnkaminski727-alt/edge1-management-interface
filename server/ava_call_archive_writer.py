#!/usr/bin/env python3
"""Append-only protected call archive writer for Ava Office.

This module owns no PBX controls and never reads or copies audio. It accepts bounded
transcript events, preserves the stream journal, and publishes immutable transcript
and manifest files under one fixed archive root.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{3,127}$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
EVENT_SPEAKERS = {"caller", "ava", "owner", "system"}
MAX_EVENT_TEXT = 16_000
MAX_JOURNAL_BYTES = 4_194_304
MAX_EVENTS = 4096
ZERO_SHA256 = "0" * 64


class AvaCallArchiveWriteError(RuntimeError):
    pass


def canonical_manifest_bytes(document: Mapping[str, Any]) -> bytes:
    """Hash representation: canonical JSON with manifest_sha256 omitted."""
    clone = json.loads(json.dumps(document))
    integrity = clone.get("integrity")
    if not isinstance(integrity, dict):
        raise AvaCallArchiveWriteError("manifest integrity metadata is invalid")
    integrity.pop("manifest_sha256", None)
    return (json.dumps(clone, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def manifest_sha256(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_manifest_bytes(document)).hexdigest()


class AvaCallArchiveWriter:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.journals = self.root / "journals"
        self.manifests = self.root / "manifests"
        self.transcripts = self.root / "transcripts"

    @staticmethod
    def _ref(value: Any, label: str) -> str:
        text = str(value or "")
        if not REF_RE.fullmatch(text):
            raise AvaCallArchiveWriteError(f"{label} is invalid")
        return text

    @staticmethod
    def _timestamp(value: Any) -> str:
        text = str(value or "").strip()
        if not text.endswith("Z"):
            raise AvaCallArchiveWriteError("timestamp must be RFC 3339 UTC")
        try:
            parsed = datetime.fromisoformat(text[:-1] + "+00:00")
        except ValueError as exc:
            raise AvaCallArchiveWriteError("timestamp must be RFC 3339 UTC") from exc
        if parsed.utcoffset() is None:
            raise AvaCallArchiveWriteError("timestamp must include UTC timezone information")
        return parsed.isoformat().replace("+00:00", "Z")

    def prepare(self) -> None:
        for path in (self.root, self.journals, self.manifests, self.transcripts):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            try:
                path.chmod(0o700)
            except OSError:
                pass

    def _journal_path(self, call_ref: str) -> Path:
        return self.journals / f"{self._ref(call_ref, 'call_ref')}.jsonl"

    def append_transcript_event(
        self,
        *,
        call_ref: str,
        event_ref: str,
        occurred_at_utc: str,
        speaker: str,
        text: str,
    ) -> dict[str, Any]:
        self.prepare()
        call = self._ref(call_ref, "call_ref")
        event = self._ref(event_ref, "event_ref")
        occurred = self._timestamp(occurred_at_utc)
        role = str(speaker or "").strip().lower()
        if role not in EVENT_SPEAKERS:
            raise AvaCallArchiveWriteError("speaker is invalid")
        body = str(text or "")
        if not body or len(body) > MAX_EVENT_TEXT or "\x00" in body:
            raise AvaCallArchiveWriteError("transcript event text is invalid")
        path = self._journal_path(call)
        if path.exists() and path.stat().st_size > MAX_JOURNAL_BYTES:
            raise AvaCallArchiveWriteError("transcript journal is too large")
        record = {
            "schema_version": 1,
            "call_ref": call,
            "event_ref": event,
            "occurred_at_utc": occurred,
            "speaker": role,
            "text": body,
        }
        encoded = (json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, encoded)
            os.fsync(fd)
        finally:
            os.close(fd)
        return {"call_ref": call, "event_ref": event, "journal_bytes": path.stat().st_size}

    def _journal_events(self, call_ref: str) -> list[dict[str, Any]]:
        path = self._journal_path(call_ref)
        if not path.is_file() or path.stat().st_size > MAX_JOURNAL_BYTES:
            raise AvaCallArchiveWriteError("transcript journal is unavailable")
        events: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    doc = json.loads(line)
                    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
                        raise AvaCallArchiveWriteError("transcript journal is invalid")
                    if self._ref(doc.get("call_ref"), "call_ref") != self._ref(call_ref, "call_ref"):
                        raise AvaCallArchiveWriteError("transcript journal call mismatch")
                    event_ref = self._ref(doc.get("event_ref"), "event_ref")
                    if event_ref in seen:
                        raise AvaCallArchiveWriteError("duplicate transcript event")
                    seen.add(event_ref)
                    self._timestamp(doc.get("occurred_at_utc"))
                    if doc.get("speaker") not in EVENT_SPEAKERS:
                        raise AvaCallArchiveWriteError("transcript journal speaker is invalid")
                    text = doc.get("text")
                    if not isinstance(text, str) or not text or len(text) > MAX_EVENT_TEXT:
                        raise AvaCallArchiveWriteError("transcript journal text is invalid")
                    events.append(doc)
                    if len(events) > MAX_EVENTS:
                        raise AvaCallArchiveWriteError("transcript journal has too many events")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AvaCallArchiveWriteError("transcript journal is invalid") from exc
        if not events:
            raise AvaCallArchiveWriteError("transcript journal is empty")
        return events

    @staticmethod
    def _render_transcript(events: Iterable[Mapping[str, Any]]) -> bytes:
        lines = []
        for event in events:
            speaker = str(event["speaker"]).capitalize()
            occurred = str(event["occurred_at_utc"])
            text = str(event["text"]).replace("\r\n", "\n").replace("\r", "\n")
            lines.append(f"[{occurred}] {speaker}: {text}")
        return ("\n".join(lines) + "\n").encode("utf-8")

    @staticmethod
    def _media_policy_ok(manifest: Mapping[str, Any]) -> None:
        recording = manifest.get("recording_policy")
        transcription = manifest.get("transcription_policy")
        if not isinstance(recording, dict) or not isinstance(transcription, dict):
            raise AvaCallArchiveWriteError("media policy is missing")
        media_enabled = bool(recording.get("enabled")) or bool(transcription.get("enabled"))
        notice_required = bool(recording.get("notice_required"))
        consent_required = bool(recording.get("consent_required"))
        consent_state = str(recording.get("consent_state") or "")
        events = manifest.get("events") if isinstance(manifest.get("events"), list) else []
        event_types = {item.get("type") for item in events if isinstance(item, dict)}
        if media_enabled and notice_required and "notice" not in event_types:
            raise AvaCallArchiveWriteError("required media notice is not recorded")
        if media_enabled and consent_required and consent_state != "granted":
            raise AvaCallArchiveWriteError("required media consent is not granted")
        if not bool(recording.get("enabled")) and manifest.get("recording_ref") is not None:
            raise AvaCallArchiveWriteError("recording reference is not allowed when recording is disabled")
        if not bool(transcription.get("enabled")) and manifest.get("transcript_ref") is not None:
            raise AvaCallArchiveWriteError("transcript reference is not allowed when transcription is disabled")

    @staticmethod
    def _atomic_create(path: Path, payload: bytes) -> None:
        if path.exists():
            raise AvaCallArchiveWriteError(f"archive object already exists: {path.name}")
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".ava-archive-", dir=str(path.parent))
        tmp = Path(tmp_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(tmp, path)
            except FileExistsError as exc:
                raise AvaCallArchiveWriteError(f"archive object already exists: {path.name}") from exc
            dir_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass

    def finalize_call(self, manifest: Mapping[str, Any]) -> dict[str, Any]:
        self.prepare()
        if not isinstance(manifest, Mapping) or manifest.get("schema_version") != 1:
            raise AvaCallArchiveWriteError("unsupported call manifest")
        doc = json.loads(json.dumps(manifest))
        call_ref = self._ref(doc.get("call_ref"), "call_ref")
        self._timestamp(doc.get("started_at_utc"))
        if doc.get("direction") not in {"inbound", "outbound", "internal"}:
            raise AvaCallArchiveWriteError("call direction is invalid")
        self._media_policy_ok(doc)
        integrity = doc.get("integrity")
        if not isinstance(integrity, dict):
            raise AvaCallArchiveWriteError("manifest integrity metadata is invalid")
        supplied_manifest_hash = integrity.get("manifest_sha256")
        if supplied_manifest_hash not in {None, "", ZERO_SHA256}:
            if not SHA256_RE.fullmatch(str(supplied_manifest_hash)):
                raise AvaCallArchiveWriteError("manifest_sha256 is invalid")
        transcript_payload: bytes | None = None
        transcript_ref: str | None = None
        if bool((doc.get("transcription_policy") or {}).get("enabled")):
            transcript_ref = self._ref(doc.get("transcript_ref"), "transcript_ref")
            events = self._journal_events(call_ref)
            transcript_payload = self._render_transcript(events)
            integrity["transcript_sha256"] = hashlib.sha256(transcript_payload).hexdigest()
        elif doc.get("transcript_ref") is not None:
            raise AvaCallArchiveWriteError("transcript reference requires transcription to be enabled")
        if doc.get("recording_ref") is not None:
            self._ref(doc.get("recording_ref"), "recording_ref")
            recording_hash = integrity.get("recording_sha256")
            if not SHA256_RE.fullmatch(str(recording_hash or "")):
                raise AvaCallArchiveWriteError("recording_sha256 is required for referenced recording")
        integrity["manifest_sha256"] = manifest_sha256(doc)
        manifest_payload = (json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        manifest_path = self.manifests / f"{call_ref}.json"
        transcript_path = self.transcripts / f"{transcript_ref}.txt" if transcript_ref else None
        if manifest_path.exists() or (transcript_path is not None and transcript_path.exists()):
            raise AvaCallArchiveWriteError("final archive object already exists")
        if transcript_path is not None and transcript_payload is not None:
            self._atomic_create(transcript_path, transcript_payload)
        try:
            self._atomic_create(manifest_path, manifest_payload)
        except Exception:
            if transcript_path is not None and transcript_path.exists() and not manifest_path.exists():
                # Preserve rather than delete published evidence; caller can reconcile the orphan.
                pass
            raise
        return {
            "call_ref": call_ref,
            "manifest_sha256": integrity["manifest_sha256"],
            "transcript_sha256": integrity.get("transcript_sha256"),
            "recording_sha256": integrity.get("recording_sha256"),
            "journal_preserved": self._journal_path(call_ref).is_file(),
            "immutable": True,
            "audio_copied": False,
        }
