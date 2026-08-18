from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Literal

from .models import Channel, MediaItem, NormalizedMessage


ScanResult = Literal["clean", "malicious", "error"]
MediaScanner = Callable[[MediaItem], ScanResult]


@dataclass(frozen=True)
class MediaQuarantineRecord:
    sha256: str | None
    content_type: str | None
    state: str
    scan_result: str | None
    release_authorized: bool = False
    source_url_exposed: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def assess_media_item(item: MediaItem, scanner: MediaScanner | None = None) -> MediaQuarantineRecord:
    """Assess metadata without fetching provider URLs or releasing content.

    The default is fail-closed. A media item is not considered clean unless a trusted
    caller supplies a scanner callback and that scanner explicitly returns ``clean``.
    Even a clean scan does not authorize quarantine release.
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
    if any(state in {"quarantined_malicious", "quarantined_scan_error", "quarantined_missing_digest"} for state in states):
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
