import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from app.media_quarantine import (
    ScannerUnavailableError,
    ingest_media_blob,
    scan_stored_media,
)
from app.models import MediaItem
from app.quarantine_storage import (
    BlobIntegrityError,
    DigestMismatchError,
    InvalidMediaMetadata,
    MediaTooLargeError,
    PrivateQuarantineStore,
    QuarantineStorageError,
)


def media(data: bytes, *, content_type: str = "image/jpeg", digest: str | None = None) -> MediaItem:
    return MediaItem(
        url="https://provider.invalid/private/object/1",
        content_type=content_type,
        sha256=digest if digest is not None else hashlib.sha256(data).hexdigest(),
    )


class Scanner:
    scanner_id = "private:test-scanner"

    def __init__(self, result="clean", error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def scan(self, blob_path, *, sha256, content_type, timeout_seconds):
        self.calls += 1
        assert blob_path.is_file()
        assert hashlib.sha256(blob_path.read_bytes()).hexdigest() == sha256
        assert 0.1 <= timeout_seconds <= 300
        if self.error is not None:
            raise self.error
        return self.result


def test_valid_blob_ingestion_is_private_and_deterministic(tmp_path):
    data = b"mms-private-media"
    item = media(data)
    store = PrivateQuarantineStore(tmp_path / "quarantine", max_bytes=1024)
    result = ingest_media_blob(item, [data[:4], data[4:]], store, original_filename="../../Camera 1.jpg")
    assert result["attachment_id"] == f"mms-sha256-{item.sha256}"
    assert result["state"] == "quarantined_pending_scan"
    assert result["release_authorized"] is False
    record = store.read_record(result["attachment_id"])
    assert record["safe_filename"] == "Camera 1.jpg"
    assert record["web_served"] is False
    assert record["release_authorized"] is False
    assert "provider.invalid" not in json.dumps(record)
    for path in (store.root, *store._dirs.values()):
        assert os.stat(path).st_mode & 0o077 == 0
    blob = store.verify_blob(result["attachment_id"])
    assert os.stat(blob).st_mode & 0o077 == 0


def test_hash_mismatch_fails_closed(tmp_path):
    store = PrivateQuarantineStore(tmp_path / "quarantine", max_bytes=1024)
    item = media(b"expected")
    with pytest.raises(DigestMismatchError):
        ingest_media_blob(item, [b"different"], store)


def test_duplicate_digest_reuses_verified_content(tmp_path):
    data = b"same-content"
    item = media(data)
    store = PrivateQuarantineStore(tmp_path / "quarantine", max_bytes=1024)
    first = ingest_media_blob(item, [data], store)
    second = ingest_media_blob(item, [data], store)
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert first["attachment_id"] == second["attachment_id"]


def test_missing_digest_cannot_enter_blob_store(tmp_path):
    store = PrivateQuarantineStore(tmp_path / "quarantine", max_bytes=1024)
    item = MediaItem(url="https://provider.invalid/private/object/2", content_type="image/png", sha256=None)
    with pytest.raises(InvalidMediaMetadata):
        ingest_media_blob(item, [b"x"], store)


def test_malformed_media_metadata_fails_closed(tmp_path):
    store = PrivateQuarantineStore(tmp_path / "quarantine", max_bytes=1024)
    item = media(b"x", content_type="image/jpeg; name=unsafe")
    with pytest.raises(InvalidMediaMetadata):
        ingest_media_blob(item, [b"x"], store)


def test_oversized_input_is_rejected(tmp_path):
    data = b"0123456789"
    store = PrivateQuarantineStore(tmp_path / "quarantine", max_bytes=5)
    with pytest.raises(MediaTooLargeError):
        ingest_media_blob(media(data), [data], store)


def stored(tmp_path, data=b"scan-me"):
    store = PrivateQuarantineStore(tmp_path / "quarantine", max_bytes=1024)
    result = ingest_media_blob(media(data), [data], store)
    return store, result["attachment_id"]


def test_scanner_unavailable_remains_held(tmp_path):
    store, attachment_id = stored(tmp_path)
    result = scan_stored_media(attachment_id, store, None)
    assert result["state"] == "quarantined_scanner_unavailable"
    assert result["release_authorized"] is False


def test_scanner_explicit_unavailable_remains_held(tmp_path):
    store, attachment_id = stored(tmp_path)
    result = scan_stored_media(
        attachment_id,
        store,
        Scanner(error=ScannerUnavailableError("offline")),
    )
    assert result["state"] == "quarantined_scanner_unavailable"


def test_scanner_timeout_remains_held(tmp_path):
    store, attachment_id = stored(tmp_path)
    result = scan_stored_media(attachment_id, store, Scanner(error=TimeoutError("timeout")))
    assert result["state"] == "quarantined_scan_timeout"
    assert result["release_authorized"] is False


def test_scanner_error_remains_held(tmp_path):
    store, attachment_id = stored(tmp_path)
    result = scan_stored_media(attachment_id, store, Scanner(error=RuntimeError("broken")))
    assert result["state"] == "quarantined_scan_error"


def test_malicious_result_remains_held(tmp_path):
    store, attachment_id = stored(tmp_path)
    result = scan_stored_media(attachment_id, store, Scanner(result="malicious"))
    assert result["state"] == "quarantined_malicious"
    assert result["verdict"] == "malicious"
    assert result["release_authorized"] is False


def test_clean_result_still_remains_held(tmp_path):
    store, attachment_id = stored(tmp_path)
    result = scan_stored_media(attachment_id, store, Scanner(result="clean"))
    assert result["state"] == "scanned_clean_held"
    assert result["verdict"] == "clean"
    assert result["release_authorized"] is False


def test_unexpected_scanner_result_fails_closed(tmp_path):
    store, attachment_id = stored(tmp_path)
    result = scan_stored_media(attachment_id, store, Scanner(result="unknown"))
    assert result["state"] == "quarantined_scan_error"
    assert result["verdict"] == "unexpected"


def test_storage_failure_does_not_report_success(tmp_path, monkeypatch):
    data = b"storage-failure"
    store = PrivateQuarantineStore(tmp_path / "quarantine", max_bytes=1024)
    original = store._atomic_json_write
    calls = {"count": 0}

    def fail_first_write(target, payload):
        calls["count"] += 1
        if calls["count"] == 1:
            raise QuarantineStorageError("simulated metadata failure")
        return original(target, payload)

    monkeypatch.setattr(store, "_atomic_json_write", fail_first_write)
    with pytest.raises(QuarantineStorageError):
        ingest_media_blob(media(data), [data], store)
    digest = hashlib.sha256(data).hexdigest()
    blob = store.root / "blobs" / "sha256" / digest[:2] / f"{digest}.blob"
    assert blob.is_file()
    assert os.stat(blob).st_mode & 0o077 == 0


def test_restart_recovery_reads_same_held_record(tmp_path):
    data = b"persistent-held-media"
    root = tmp_path / "quarantine"
    first = PrivateQuarantineStore(root, max_bytes=1024)
    result = ingest_media_blob(media(data), [data], first)
    attachment_id = result["attachment_id"]
    first = None
    second = PrivateQuarantineStore(root, max_bytes=1024)
    recovered = second.read_record(attachment_id)
    assert recovered["state"] == "quarantined_pending_scan"
    assert recovered["release_authorized"] is False
    assert second.verify_blob(attachment_id).read_bytes() == data


def test_retention_expiry_never_auto_releases_or_deletes(tmp_path):
    data = b"retained"
    start = datetime(2026, 8, 18, tzinfo=timezone.utc)
    store = PrivateQuarantineStore(tmp_path / "quarantine", max_bytes=1024, retention_days=1)
    result = store.ingest_chunks([data], expected_sha256=hashlib.sha256(data).hexdigest(), now=start)
    later = start + timedelta(days=2)
    record = store.read_record(result.attachment_id, now=later)
    assert record["lifecycle_state"] == "retention_expired_held"
    assert record["release_authorized"] is False
    assert result.attachment_id in store.retention_candidates(now=later)
    assert store.verify_blob(result.attachment_id).is_file()


def test_integrity_mutation_fails_closed(tmp_path):
    store, attachment_id = stored(tmp_path, b"original")
    blob = store.verify_blob(attachment_id)
    blob.write_bytes(b"tampered")
    os.chmod(blob, 0o600)
    result = scan_stored_media(attachment_id, store, Scanner(result="clean"))
    assert result["state"] == "quarantined_integrity_error"
    assert result["release_authorized"] is False
    with pytest.raises(BlobIntegrityError):
        store.verify_blob(attachment_id)


def test_symlink_root_is_rejected(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(QuarantineStorageError):
        PrivateQuarantineStore(link)
