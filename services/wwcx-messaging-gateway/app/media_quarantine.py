from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Literal, Protocol, runtime_checkable

from .models import Channel, MediaItem, NormalizedMessage
from .quarantine_storage import (
    BlobIntegrityError,
    InvalidMediaMetadata,
    PrivateQuarantineStore,
    normalize_scanner_id,
)

ScanResult = Literal["clean", "malicious", "error"]
MediaScanner = Callable[[MediaItem], ScanResult]
TrustedScanVerdict = Literal["clean", "malicious"]


class ScannerUnavailableError(RuntimeError):
    pass


@runtime_checkable
class TrustedMediaScanner(Protocol):
    """Narrow adapter contract for an established private scanner runtime.

    Implementations must enforce their own timeout and must not upload content unless
    that external processing path has been separately authorized. This repository does
    not provide a generic shell-command scanner implementation.
    """

    scanner_id: str

    def scan(
        self,
        blob_path: Path,
        *,
        sha256: str,
        content_type: str | None,
        timeout_seconds: float,
    ) -> TrustedScanVerdict:
        ...


@dataclass(frozen=True)
class MediaQuarantineRecord:
    sha256: str | None
    content_type: str | None
    state: str
    scan_result: str | None
    release_authorized: bool = False
    provider_reference_exposed: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def assess_media_item(item: MediaItem, scanner: MediaScanner | None = None) -> MediaQuarantineRecord:
    """Assess provider metadata only; this is not runtime malware-scanner evidence.

    The fail-closed compatibility helper never fetches or stores provider media. Real
    attachment processing must use ``ingest_media_blob`` plus ``scan_stored_media`` so
    scanner input is a digest-verified private blob. Even a clean result never releases
    an attachment.
    """
    if not item.sha256:
        return MediaQuarantineRecord(
            sha256=None,
            content_type=item.content_type,
            state="quarantined_missing_digest",
            scan_result=None,
        )
    if scanner is None:
        return MediaQuarantineRecord(
            sha256=item.sha256.lower(),
            content_type=item.content_type,
            state="quarantined_pending_scan",
            scan_result=None,
        )
    try:
        result = scanner(item)
    except Exception:
        result = "error"
    if result == "clean":
        state = "scanned_clean_held"
    elif result == "malicious":
        state = "quarantined_malicious"
    else:
        state = "quarantined_scan_error"
        result = "error"
    return MediaQuarantineRecord(
        sha256=item.sha256.lower(),
        content_type=item.content_type,
        state=state,
        scan_result=result,
    )


def ingest_media_blob(
    item: MediaItem,
    chunks: Iterable[bytes],
    store: PrivateQuarantineStore,
    *,
    original_filename: str | None = None,
) -> dict[str, object]:
    """Store a provider-supplied MMS blob only after bounded SHA-256 verification."""
    if not item.sha256:
        raise InvalidMediaMetadata(
            "MMS media without a SHA-256 digest remains quarantined and cannot be ingested"
        )
    return store.ingest_chunks(
        chunks,
        expected_sha256=item.sha256,
        content_type=item.content_type,
        original_filename=original_filename,
    ).to_dict()


def _integrity_failure_record(
    attachment_id: str,
    scanner_id: str | None,
) -> dict[str, object]:
    """Return a held result when the trusted blob/state cannot safely be updated."""
    return {
        "attachment_id": attachment_id,
        "state": "quarantined_integrity_error",
        "verdict": "integrity_error",
        "scanner_id": scanner_id,
        "release_authorized": False,
        "web_served": False,
    }


def scan_stored_media(
    attachment_id: str,
    store: PrivateQuarantineStore,
    scanner: TrustedMediaScanner | None,
    *,
    timeout_seconds: float = 15.0,
) -> dict[str, object]:
    """Scan a verified private blob through a trusted adapter and keep it held.

    Tests may use controlled doubles for this interface. A test double is never evidence
    that a production scanner exists. The adapter is responsible for enforcing its own
    timeout; timeout/unavailability/error/unknown verdicts all fail closed.
    """
    if not isinstance(timeout_seconds, (int, float)) or not 0.1 <= float(timeout_seconds) <= 300:
        raise ValueError("scanner timeout must be between 0.1 and 300 seconds")

    raw_scanner_id = getattr(scanner, "scanner_id", None) if scanner is not None else None
    try:
        scanner_id = normalize_scanner_id(raw_scanner_id)
    except InvalidMediaMetadata:
        scanner_id = None
        scanner = None

    try:
        record = store.read_record(attachment_id)
    except BlobIntegrityError:
        return _integrity_failure_record(attachment_id, scanner_id)

    if scanner is None:
        return store.record_scan_state(
            attachment_id,
            state="quarantined_scanner_unavailable",
            verdict=None,
            scanner_id=scanner_id,
        )

    try:
        blob_path = store.verify_blob(attachment_id)
        result = scanner.scan(
            blob_path,
            sha256=str(record["sha256"]),
            content_type=(
                record.get("content_type")
                if isinstance(record.get("content_type"), str)
                else None
            ),
            timeout_seconds=float(timeout_seconds),
        )
        # Re-verify after the scanner returns to fail closed on unexpected mutation.
        store.verify_blob(attachment_id)
    except ScannerUnavailableError:
        return store.record_scan_state(
            attachment_id,
            state="quarantined_scanner_unavailable",
            verdict=None,
            scanner_id=scanner_id,
        )
    except TimeoutError:
        return store.record_scan_state(
            attachment_id,
            state="quarantined_scan_timeout",
            verdict="timeout",
            scanner_id=scanner_id,
        )
    except BlobIntegrityError:
        return _integrity_failure_record(attachment_id, scanner_id)
    except Exception:
        return store.record_scan_state(
            attachment_id,
            state="quarantined_scan_error",
            verdict="error",
            scanner_id=scanner_id,
        )

    if result == "clean":
        return store.record_scan_state(
            attachment_id,
            state="scanned_clean_held",
            verdict="clean",
            scanner_id=scanner_id,
        )
    if result == "malicious":
        return store.record_scan_state(
            attachment_id,
            state="quarantined_malicious",
            verdict="malicious",
            scanner_id=scanner_id,
        )
    return store.record_scan_state(
        attachment_id,
        state="quarantined_scan_error",
        verdict="unexpected",
        scanner_id=scanner_id,
    )


def quarantine_summary(message: NormalizedMessage, scanner: MediaScanner | None = None) -> dict[str, object]:
    if message.channel == Channel.SMS or not message.media:
        return {
            "applicable": False,
            "state": "not_applicable",
            "items": [],
            "release_authorized": False,
        }
    records = [assess_media_item(item, scanner) for item in message.media[:16]]
    states = {record.state for record in records}
    if any(
        state
        in {
            "quarantined_malicious",
            "quarantined_scan_error",
            "quarantined_missing_digest",
        }
        for state in states
    ):
        overall = "quarantined"
    elif "quarantined_pending_scan" in states:
        overall = "quarantined_pending_scan"
    elif states == {"scanned_clean_held"}:
        overall = "scanned_clean_held"
    else:
        overall = "quarantined"
    return {
        "applicable": True,
        "state": overall,
        "items": [record.to_dict() for record in records],
        "release_authorized": False,
    }
