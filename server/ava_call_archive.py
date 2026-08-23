#!/usr/bin/env python3
"""Read-only access to protected Ava call manifests and transcript text.

The archive adapter never reads audio, never mutates the archive, and resolves all
references through fixed subdirectories under one configured root. It is intended
for the loopback-only Ava Office service, not the aggregate telephony analytics API.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{3,127}$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
MAX_MANIFEST_BYTES = 262_144
MAX_TRANSCRIPT_BYTES = 1_048_576
MAX_LIMIT = 100


class AvaCallArchiveError(RuntimeError):
    pass


def canonical_manifest_bytes(document: Mapping[str, Any]) -> bytes:
    """Canonical hash representation with manifest_sha256 omitted."""
    clone = json.loads(json.dumps(document))
    integrity = clone.get("integrity")
    if not isinstance(integrity, dict):
        raise AvaCallArchiveError("call manifest integrity metadata is invalid")
    integrity.pop("manifest_sha256", None)
    return (json.dumps(clone, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def manifest_sha256(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_manifest_bytes(document)).hexdigest()


class AvaCallArchiveReadModel:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.manifests = self.root / "manifests"
        self.transcripts = self.root / "transcripts"

    @staticmethod
    def _limit(limit: int) -> int:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
            raise AvaCallArchiveError("limit is out of bounds")
        return limit

    @staticmethod
    def _ref(value: Any, label: str) -> str:
        text = str(value or "")
        if not REF_RE.fullmatch(text):
            raise AvaCallArchiveError(f"{label} is invalid")
        return text

    @staticmethod
    def _safe_text(value: Any, limit: int = 128) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if len(text) > limit or any(ord(ch) < 32 and ch not in "\t\n\r" for ch in text):
            raise AvaCallArchiveError("manifest contains invalid text")
        return text

    def health(self) -> dict[str, Any]:
        available = self.root.is_dir() and self.manifests.is_dir()
        count = 0
        if available:
            count = sum(1 for path in self.manifests.iterdir() if path.is_file() and path.suffix == ".json")
        return {"status": "ok" if available else "unavailable", "mode": "read-only", "archive_available": available, "manifest_count": count}

    def _manifest_path(self, call_ref: str) -> Path:
        ref = self._ref(call_ref, "call_ref")
        return self.manifests / f"{ref}.json"

    def _load_manifest_path(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise AvaCallArchiveError("call manifest is unavailable")
        if path.stat().st_size > MAX_MANIFEST_BYTES:
            raise AvaCallArchiveError("call manifest is too large")
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AvaCallArchiveError("call manifest is invalid") from exc
        if not isinstance(doc, dict) or doc.get("schema_version") != 1:
            raise AvaCallArchiveError("unsupported call manifest")
        call_ref = self._ref(doc.get("call_ref"), "call_ref")
        if path.name != f"{call_ref}.json":
            raise AvaCallArchiveError("call manifest filename mismatch")
        started = self._safe_text(doc.get("started_at_utc"), 64)
        direction = self._safe_text(doc.get("direction"), 16)
        if not started or direction not in {"inbound", "outbound", "internal"}:
            raise AvaCallArchiveError("call manifest is incomplete")
        integrity = doc.get("integrity")
        if not isinstance(integrity, dict):
            raise AvaCallArchiveError("call manifest integrity metadata is invalid")
        expected = str(integrity.get("manifest_sha256", ""))
        if not SHA256_RE.fullmatch(expected) or manifest_sha256(doc) != expected:
            raise AvaCallArchiveError("call manifest integrity check failed")
        return doc

    def manifest(self, call_ref: str) -> dict[str, Any]:
        return self._load_manifest_path(self._manifest_path(call_ref))

    def _transcript_ref(self, doc: dict[str, Any]) -> str | None:
        value = doc.get("transcript_ref")
        if value is None:
            segments = doc.get("segments") if isinstance(doc.get("segments"), list) else []
            for segment in segments:
                if isinstance(segment, dict) and segment.get("kind") == "voicemail" and segment.get("transcript_ref"):
                    value = segment.get("transcript_ref")
                    break
        if value is None:
            return None
        return self._ref(value, "transcript_ref")

    def _summary(self, doc: dict[str, Any]) -> dict[str, Any]:
        segments = doc.get("segments") if isinstance(doc.get("segments"), list) else []
        voicemail_segments = [item for item in segments if isinstance(item, dict) and item.get("kind") == "voicemail"]
        transcript_ref = self._transcript_ref(doc)
        return {
            "call_ref": self._ref(doc.get("call_ref"), "call_ref"),
            "started_at_utc": self._safe_text(doc.get("started_at_utc"), 64),
            "answered_at_utc": self._safe_text(doc.get("answered_at_utc"), 64),
            "ended_at_utc": self._safe_text(doc.get("ended_at_utc"), 64),
            "direction": self._safe_text(doc.get("direction"), 16),
            "caller_ref": self._safe_text(doc.get("caller_ref"), 128),
            "called_party_ref": self._safe_text(doc.get("called_party_ref"), 128),
            "disposition": self._safe_text(doc.get("disposition"), 64),
            "voicemail": bool(voicemail_segments),
            "recording_available": doc.get("recording_ref") is not None,
            "transcript_available": transcript_ref is not None and (self.transcripts / f"{transcript_ref}.txt").is_file(),
            "summary_available": doc.get("summary_ref") is not None,
        }

    def calls(self, *, limit: int = 50) -> list[dict[str, Any]]:
        self._limit(limit)
        if not self.manifests.is_dir():
            raise AvaCallArchiveError("call archive is unavailable")
        rows: list[dict[str, Any]] = []
        for path in self.manifests.iterdir():
            if not path.is_file() or path.suffix != ".json":
                continue
            rows.append(self._summary(self._load_manifest_path(path)))
        rows.sort(key=lambda item: str(item.get("started_at_utc") or ""), reverse=True)
        return rows[:limit]

    def voicemails(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return [item for item in self.calls(limit=MAX_LIMIT) if item["voicemail"]][: self._limit(limit)]

    def transcript(self, call_ref: str, *, max_chars: int = 20_000) -> dict[str, Any]:
        if isinstance(max_chars, bool) or not isinstance(max_chars, int) or not 1 <= max_chars <= 100_000:
            raise AvaCallArchiveError("max_chars is out of bounds")
        doc = self.manifest(call_ref)
        ref = self._transcript_ref(doc)
        if ref is None:
            raise AvaCallArchiveError("transcript is unavailable")
        path = self.transcripts / f"{ref}.txt"
        if not path.is_file() or path.stat().st_size > MAX_TRANSCRIPT_BYTES:
            raise AvaCallArchiveError("transcript is unavailable")
        raw = path.read_bytes()
        expected = (doc.get("integrity") or {}).get("transcript_sha256")
        verified = False
        if expected is not None:
            if not SHA256_RE.fullmatch(str(expected)) or hashlib.sha256(raw).hexdigest() != expected:
                raise AvaCallArchiveError("transcript integrity check failed")
            verified = True
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AvaCallArchiveError("transcript is not UTF-8") from exc
        return {
            "call_ref": self._ref(doc.get("call_ref"), "call_ref"),
            "transcript_ref": ref,
            "text": text[:max_chars],
            "truncated": len(text) > max_chars,
            "sha256_verified": verified,
            "privacy": "protected_evidence",
            "audio_exposed": False,
        }
