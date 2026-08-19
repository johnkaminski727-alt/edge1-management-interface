#!/usr/bin/env python3
"""Local-only synthetic acceptance probe for the private MMS quarantine.

This script does not contact a carrier or provider and cannot release quarantined media.
Run it only as the actual Messaging Gateway service identity after the private root and
trusted local ClamAV runtime have been reviewed on Edge1.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from app.media_quarantine import ingest_media_blob, scan_stored_media
from app.models import MediaItem
from app.quarantine_storage import PrivateQuarantineStore
from app.trusted_scanner import ClamAVScanner


DEFAULT_ROOT = Path("/var/lib/wwcx-messaging-gateway/private-mms-quarantine")


def item(data: bytes, content_type: str) -> MediaItem:
    return MediaItem(
        url="https://synthetic.invalid/not-fetched",
        content_type=content_type,
        sha256=hashlib.sha256(data).hexdigest(),
    )


def eicar_bytes() -> bytes:
    # Deliberately assembled from fragments so the repository itself does not contain
    # the complete EICAR signature. The generated runtime artifact is synthetic only.
    fragments = [
        b"X5O!P%@AP[4\\PZX54(P^)",
        b"7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$",
        b"H+H*",
    ]
    return b"".join(fragments)


def main() -> int:
    root = DEFAULT_ROOT
    store = PrivateQuarantineStore(root, max_bytes=16 * 1024 * 1024, retention_days=30)
    scanner = ClamAVScanner()

    clean = b"WW.CX synthetic clean MMS acceptance artifact\n"
    clean_ingest = ingest_media_blob(
        item(clean, "text/plain"), [clean], store, original_filename="synthetic-clean.txt"
    )
    clean_scan = scan_stored_media(clean_ingest["attachment_id"], store, scanner)
    assert clean_scan["state"] == "scanned_clean_held", clean_scan
    assert clean_scan["release_authorized"] is False

    eicar = eicar_bytes()
    eicar_ingest = ingest_media_blob(
        item(eicar, "application/octet-stream"),
        [eicar],
        store,
        original_filename="synthetic-eicar.com",
    )
    eicar_scan = scan_stored_media(eicar_ingest["attachment_id"], store, scanner)
    assert eicar_scan["state"] == "quarantined_malicious", eicar_scan
    assert eicar_scan["release_authorized"] is False

    restarted = PrivateQuarantineStore(root, max_bytes=16 * 1024 * 1024, retention_days=30)
    clean_recovered = restarted.read_record(clean_ingest["attachment_id"])
    eicar_recovered = restarted.read_record(eicar_ingest["attachment_id"])
    assert clean_recovered["state"] == "scanned_clean_held"
    assert eicar_recovered["state"] == "quarantined_malicious"
    assert clean_recovered["release_authorized"] is False
    assert eicar_recovered["release_authorized"] is False

    private_directories = (
        root,
        *(path for path in root.rglob("*") if path.is_dir()),
    )
    for path in private_directories:
        assert os.stat(path).st_mode & 0o077 == 0, path
    assert os.stat(store.verify_blob(clean_ingest["attachment_id"])).st_mode & 0o077 == 0
    assert os.stat(store.verify_blob(eicar_ingest["attachment_id"])).st_mode & 0o077 == 0

    print("private MMS quarantine local acceptance passed")
    print(f"root={root}")
    print("clean=scanned_clean_held")
    print("eicar=quarantined_malicious")
    print("restart_recovery=held")
    print("release_authorized=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
