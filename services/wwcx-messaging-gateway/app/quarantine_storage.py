from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

_DIGEST_RE = re.compile(r"^[a-fA-F0-9]{64}$")
_CONTENT_TYPE_RE = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")
_SCANNER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,127}$")
_ALLOWED_SCAN_STATES = {
    "quarantined_pending_scan", "quarantined_scanner_unavailable", "quarantined_scan_timeout",
    "quarantined_scan_error", "quarantined_malicious", "scanned_clean_held",
    "quarantined_integrity_error", "quarantined_scan_state_missing",
}

class QuarantineStorageError(RuntimeError): pass
class InvalidMediaMetadata(QuarantineStorageError): pass
class DigestMismatchError(QuarantineStorageError): pass
class MediaTooLargeError(QuarantineStorageError): pass
class BlobIntegrityError(QuarantineStorageError): pass

@dataclass(frozen=True)
class IngestResult:
    attachment_id: str
    sha256: str
    byte_count: int
    duplicate: bool
    state: str
    release_authorized: bool = False
    def to_dict(self) -> dict[str, object]:
        return {"attachment_id": self.attachment_id, "sha256": self.sha256, "byte_count": self.byte_count,
                "duplicate": self.duplicate, "state": self.state, "release_authorized": False}

def _utcnow() -> datetime: return datetime.now(timezone.utc)
def _iso(value: datetime) -> str: return value.astimezone(timezone.utc).isoformat(timespec="seconds")

def normalize_digest(value: str | None) -> str:
    if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
        raise InvalidMediaMetadata("a canonical SHA-256 digest is required")
    return value.lower()

def attachment_id_for_digest(digest: str) -> str: return f"mms-sha256-{normalize_digest(digest)}"
def _digest_from_attachment_id(attachment_id: str) -> str:
    prefix = "mms-sha256-"
    if not isinstance(attachment_id, str) or not attachment_id.startswith(prefix):
        raise InvalidMediaMetadata("attachment identifier is invalid")
    return normalize_digest(attachment_id[len(prefix):])

def normalize_content_type(value: str | None) -> str | None:
    if value is None: return None
    if not isinstance(value, str): raise InvalidMediaMetadata("content type must be text")
    normalized = value.strip()
    if len(normalized) > 127 or not _CONTENT_TYPE_RE.fullmatch(normalized):
        raise InvalidMediaMetadata("content type is malformed")
    return normalized.lower()

def safe_filename(value: str | None) -> str | None:
    if value is None: return None
    if not isinstance(value, str): raise InvalidMediaMetadata("filename must be text")
    leaf = value.replace("\\", "/").rsplit("/", 1)[-1]
    leaf = "".join(ch if 32 <= ord(ch) < 127 else "_" for ch in leaf)
    leaf = re.sub(r"[^A-Za-z0-9._ -]+", "_", leaf).strip(" .")[:120]
    return leaf or None

def normalize_scanner_id(value: str | None) -> str | None:
    if value is None: return None
    if not isinstance(value, str) or not _SCANNER_ID_RE.fullmatch(value):
        raise InvalidMediaMetadata("scanner identity is invalid")
    return value

class PrivateQuarantineStore:
    """Content-addressed, private, fail-closed storage for quarantined MMS media.

    Provider URLs/names never determine storage paths. Metadata and scan state are
    separate. This store never serves content and never authorizes quarantine release.
    """
    def __init__(self, root: str | Path, *, max_bytes: int = 16 * 1024 * 1024, retention_days: int = 30) -> None:
        if not isinstance(max_bytes, int) or not 1 <= max_bytes <= 100 * 1024 * 1024:
            raise ValueError("max_bytes must be between 1 and 100 MiB")
        if not isinstance(retention_days, int) or not 1 <= retention_days <= 730:
            raise ValueError("retention_days must be between 1 and 730")
        requested = Path(root)
        if requested.exists() and requested.is_symlink():
            raise QuarantineStorageError("quarantine root may not be a symlink")
        self.root = requested.absolute(); self.max_bytes = max_bytes; self.retention_days = retention_days
        self._dirs = {"blobs": self.root/"blobs"/"sha256", "metadata": self.root/"metadata"/"sha256",
                      "scan_state": self.root/"scan-state"/"sha256", "tmp": self.root/"tmp", "audit": self.root/"audit"}
        self._prepare_private_tree()

    def _prepare_private_tree(self) -> None:
        self._ensure_private_directory(self.root)
        for path in self._dirs.values(): self._ensure_private_directory(path)
    @staticmethod
    def _ensure_private_directory(path: Path) -> None:
        if path.exists() and path.is_symlink(): raise QuarantineStorageError(f"private path may not be a symlink: {path}")
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink() or not path.is_dir(): raise QuarantineStorageError(f"private path is not a directory: {path}")
        os.chmod(path, 0o700)
    def _shard(self, kind: str, digest: str) -> Path:
        digest = normalize_digest(digest); directory = self._dirs[kind] / digest[:2]
        self._ensure_private_directory(directory); return directory
    def _blob_path(self, digest: str) -> Path: return self._shard("blobs", digest) / f"{normalize_digest(digest)}.blob"
    def _metadata_path(self, digest: str) -> Path: return self._shard("metadata", digest) / f"{normalize_digest(digest)}.json"
    def _scan_state_path(self, digest: str) -> Path: return self._shard("scan_state", digest) / f"{normalize_digest(digest)}.json"
    @staticmethod
    def _assert_regular_private_file(path: Path) -> None:
        try: info = path.lstat()
        except FileNotFoundError as exc: raise BlobIntegrityError("required quarantine file is missing") from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode): raise BlobIntegrityError("quarantine path is not a regular file")
        if info.st_mode & 0o077: raise BlobIntegrityError("quarantine file permissions are too broad")
    @staticmethod
    def _read_json(path: Path) -> dict[str, object]:
        PrivateQuarantineStore._assert_regular_private_file(path)
        try: data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc: raise BlobIntegrityError("quarantine metadata is unreadable") from exc
        if not isinstance(data, dict): raise BlobIntegrityError("quarantine metadata must be an object")
        return data
    def _atomic_json_write(self, target: Path, data: dict[str, object]) -> None:
        self._ensure_private_directory(target.parent); fd = -1; temp_path: Path | None = None
        try:
            fd, name = tempfile.mkstemp(prefix=".write-", suffix=".tmp", dir=str(target.parent)); temp_path = Path(name); os.fchmod(fd, 0o600)
            encoded = (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            with os.fdopen(fd, "wb", closefd=True) as handle:
                fd = -1; handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
            os.replace(temp_path, target); temp_path = None; os.chmod(target, 0o600)
        except OSError as exc: raise QuarantineStorageError("failed to persist quarantine metadata") from exc
        finally:
            if fd >= 0: os.close(fd)
            if temp_path is not None:
                try: temp_path.unlink(missing_ok=True)
                except OSError: pass
    def _audit(self, event: str, **fields: object) -> None:
        payload = {"event": event, "occurred_at": _iso(_utcnow()), **fields}; target = self._dirs["audit"] / "quarantine-audit.jsonl"
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.fchmod(fd, 0o600); os.write(fd, (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")); os.fsync(fd)
            finally: os.close(fd)
        except OSError as exc: raise QuarantineStorageError("failed to write quarantine audit event") from exc

    def ingest_chunks(self, chunks: Iterable[bytes], *, expected_sha256: str | None, content_type: str | None = None,
                      original_filename: str | None = None, now: datetime | None = None) -> IngestResult:
        digest = normalize_digest(expected_sha256); normalized_type = normalize_content_type(content_type); normalized_name = safe_filename(original_filename)
        attachment_id = attachment_id_for_digest(digest); observed_at = (now or _utcnow()).astimezone(timezone.utc)
        fd = -1; temp_path: Path | None = None; byte_count = 0; hasher = hashlib.sha256()
        try:
            fd, name = tempfile.mkstemp(prefix="ingest-", suffix=".blob", dir=str(self._dirs["tmp"])); temp_path = Path(name); os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as handle:
                fd = -1
                for chunk in chunks:
                    if not isinstance(chunk, (bytes, bytearray, memoryview)): raise InvalidMediaMetadata("media chunks must contain bytes")
                    data = bytes(chunk)
                    if not data: continue
                    byte_count += len(data)
                    if byte_count > self.max_bytes: raise MediaTooLargeError("media exceeds configured quarantine size limit")
                    hasher.update(data); handle.write(data)
                handle.flush(); os.fsync(handle.fileno())
        except QuarantineStorageError: raise
        except OSError as exc: raise QuarantineStorageError("failed to write quarantined media") from exc
        finally:
            if fd >= 0: os.close(fd)
        actual = hasher.hexdigest()
        if actual != digest:
            if temp_path is not None: temp_path.unlink(missing_ok=True)
            self._audit("mms_quarantine_digest_mismatch", attachment_id=attachment_id, expected_sha256=digest,
                        actual_sha256=actual, byte_count=byte_count, release_authorized=False)
            raise DigestMismatchError("quarantined media digest does not match expected SHA-256")
        blob_path = self._blob_path(digest); metadata_path = self._metadata_path(digest); scan_state_path = self._scan_state_path(digest); duplicate = False
        try:
            try: os.link(temp_path, blob_path); os.chmod(blob_path, 0o600)
            except FileExistsError: duplicate = True
            except OSError as exc:
                if exc.errno == errno.EEXIST: duplicate = True
                else: raise QuarantineStorageError("failed to finalize quarantined media") from exc
        finally:
            if temp_path is not None: temp_path.unlink(missing_ok=True)
        if duplicate:
            self.verify_blob(attachment_id); metadata = self._read_json(metadata_path); state = self._read_json(scan_state_path)
            if metadata.get("sha256") != digest or state.get("sha256") != digest: raise BlobIntegrityError("duplicate quarantine metadata does not match content digest")
            current_state = str(state.get("state", "quarantined_scan_state_missing"))
            self._audit("mms_quarantine_duplicate", attachment_id=attachment_id, sha256=digest, byte_count=byte_count,
                        state=current_state, release_authorized=False)
            return IngestResult(attachment_id, digest, byte_count, True, current_state)
        retention_until = observed_at + timedelta(days=self.retention_days)
        metadata = {"contract": "wwcx.mms-private-quarantine-blob.v1", "attachment_id": attachment_id, "sha256": digest,
                    "byte_count": byte_count, "content_type": normalized_type, "safe_filename": normalized_name,
                    "stored_at": _iso(observed_at), "retention_expires_at": _iso(retention_until),
                    "storage_class": "private_quarantine", "web_served": False}
        scan_state = {"contract": "wwcx.mms-private-quarantine-scan.v1", "attachment_id": attachment_id, "sha256": digest,
                      "state": "quarantined_pending_scan", "verdict": None, "scanner_id": None, "scanned_at": None,
                      "release_authorized": False}
        self._atomic_json_write(metadata_path, metadata); self._atomic_json_write(scan_state_path, scan_state)
        self._audit("mms_quarantine_ingested", attachment_id=attachment_id, sha256=digest, byte_count=byte_count,
                    state="quarantined_pending_scan", release_authorized=False)
        return IngestResult(attachment_id, digest, byte_count, False, "quarantined_pending_scan")

    def verify_blob(self, attachment_id: str) -> Path:
        digest = _digest_from_attachment_id(attachment_id); target = self._blob_path(digest); self._assert_regular_private_file(target)
        metadata = self._read_json(self._metadata_path(digest)); expected_size = metadata.get("byte_count")
        if not isinstance(expected_size, int) or expected_size < 0 or expected_size > self.max_bytes: raise BlobIntegrityError("quarantine byte count metadata is invalid")
        hasher = hashlib.sha256(); total = 0
        try:
            with target.open("rb") as handle:
                while True:
                    chunk = handle.read(64 * 1024)
                    if not chunk: break
                    total += len(chunk)
                    if total > self.max_bytes: raise BlobIntegrityError("quarantined media exceeds configured size limit")
                    hasher.update(chunk)
        except OSError as exc: raise BlobIntegrityError("quarantined media cannot be read") from exc
        if total != expected_size or hasher.hexdigest() != digest: raise BlobIntegrityError("quarantined media failed integrity verification")
        return target

    def read_record(self, attachment_id: str, *, now: datetime | None = None) -> dict[str, object]:
        digest = _digest_from_attachment_id(attachment_id); self.verify_blob(attachment_id); metadata = self._read_json(self._metadata_path(digest))
        try: state = self._read_json(self._scan_state_path(digest))
        except BlobIntegrityError:
            state = {"state": "quarantined_scan_state_missing", "verdict": None, "scanner_id": None, "scanned_at": None}
        expires_at = datetime.fromisoformat(str(metadata["retention_expires_at"])); current = (now or _utcnow()).astimezone(timezone.utc)
        return {"attachment_id": attachment_id, "sha256": digest, "content_type": metadata.get("content_type"),
                "safe_filename": metadata.get("safe_filename"), "byte_count": metadata.get("byte_count"), "stored_at": metadata.get("stored_at"),
                "retention_expires_at": metadata.get("retention_expires_at"),
                "lifecycle_state": "retention_expired_held" if current >= expires_at else "retained_held",
                "state": state.get("state", "quarantined_scan_state_missing"), "verdict": state.get("verdict"),
                "scanner_id": state.get("scanner_id"), "scanned_at": state.get("scanned_at"), "release_authorized": False, "web_served": False}

    def record_scan_state(self, attachment_id: str, *, state: str, verdict: str | None, scanner_id: str | None,
                          now: datetime | None = None) -> dict[str, object]:
        if state not in _ALLOWED_SCAN_STATES: raise InvalidMediaMetadata("scan state is not recognized")
        digest = _digest_from_attachment_id(attachment_id); self.verify_blob(attachment_id); normalized_scanner = normalize_scanner_id(scanner_id)
        scanned_at = None if state in {"quarantined_pending_scan", "quarantined_scanner_unavailable"} else _iso(now or _utcnow())
        payload = {"contract": "wwcx.mms-private-quarantine-scan.v1", "attachment_id": attachment_id, "sha256": digest,
                   "state": state, "verdict": verdict, "scanner_id": normalized_scanner, "scanned_at": scanned_at, "release_authorized": False}
        self._atomic_json_write(self._scan_state_path(digest), payload)
        self._audit("mms_quarantine_scan_state", attachment_id=attachment_id, sha256=digest, state=state, verdict=verdict,
                    scanner_id=normalized_scanner, release_authorized=False)
        return self.read_record(attachment_id)

    def retention_candidates(self, *, now: datetime | None = None) -> list[str]:
        """Return expired held IDs for explicit lifecycle processing; never delete automatically."""
        current = (now or _utcnow()).astimezone(timezone.utc); candidates: list[str] = []
        for target in self._dirs["metadata"].glob("*/*.json"):
            try:
                data = self._read_json(target); expires_at = datetime.fromisoformat(str(data["retention_expires_at"])); attachment_id = str(data["attachment_id"])
                if current >= expires_at: candidates.append(attachment_id)
            except (BlobIntegrityError, KeyError, ValueError): continue
        return sorted(set(candidates))
