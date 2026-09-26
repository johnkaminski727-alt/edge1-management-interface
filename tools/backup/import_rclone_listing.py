#!/usr/bin/env python3
"""Import an operator-supplied rclone lsjson Dropbox listing as *upload-only* evidence.

No Dropbox credentials, archive contents or network access are used. Intended
to consume a fresh listing generated locally on Edge1 by an authorized operator.
Never asserts archive integrity or restore success.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

NAME = re.compile(r"^edge1-(\d{8}T\d{6}Z)\.tar\.gz\.gpg$")
MAX_LISTING_BYTES = 2_000_000
MAX_ARCHIVES = 1000
EXPECTED_PARENT = "Edge1-Recovery/daily/"

def parse_listing(raw):
    """Returns sanitized records for exact-path encrypted archives only."""
    if not isinstance(raw, list) or len(raw) > MAX_ARCHIVES:
        raise ValueError("Expected a bounded rclone lsjson array")
    results = {}
    for item in raw:
        if not isinstance(item, dict) or item.get("IsDir") is not False:
            continue
        path = item.get("Path")
        if not isinstance(path, str):
            continue
        # Also accept lsjson invoked from the daily directory (basename).
        if path.startswith(EXPECTED_PARENT):
            name = path[len(EXPECTED_PARENT):]
        elif "/" not in path:
            name = path
        else:
            continue
        match = NAME.fullmatch(name)
        if not match:
            continue
        try:
            created = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        size = item.get("Size")
        if type(size) is not int or size < 1 or size > 10**13:
            continue
        # Listing establishes remote existence only; no proof of checksum or restore.
        results[name] = {
            "archive": name,
            "created_at": created.isoformat().replace("+00:00", "Z"),
            "size_bytes": size,
            "upload": "uploaded",
            "integrity": "unknown",
            "restore_test": "unknown",
        }
    return sorted(results.values(), key=lambda r: r["created_at"], reverse=True)

def write_manifests(records, destination):
    if not destination.is_dir() or destination.is_symlink():
        raise ValueError("Manifest directory must already exist and not be a symlink")
    if destination.stat().st_mode & 0o022:
        raise ValueError("Manifest directory cannot be group/world writable")
    for record in records:
        target = destination / (record["archive"] + ".json")
        # Never follow existing symlinks and never modify any verified record.
        if target.is_symlink() or target.exists():
            continue
        fd, tmpname = tempfile.mkstemp(prefix=".pending-", suffix=".json", dir=destination)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump(record, stream, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmpname, target)
        finally:
            if os.path.exists(tmpname):
                os.unlink(tmpname)
    return len(records)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--listing", type=Path, required=True,
                   help="Locally generated rclone lsjson listing of Edge1-Recovery/daily")
    p.add_argument("--manifest-dir", type=Path, required=True,
                   help="Existing restricted destination for sanitized manifests")
    p.add_argument("--dry-run", action="store_true", help="Validate and report count only")
    args = p.parse_args()
    if args.listing.is_symlink() or not args.listing.is_file() or args.listing.stat().st_size > MAX_LISTING_BYTES:
        p.error("Listing must be a regular file <=2MB")
    try:
        records = parse_listing(json.loads(args.listing.read_text(encoding="utf-8")))
        if not args.dry_run:
            write_manifests(records, args.manifest_dir)
    except (ValueError, OSError, UnicodeError) as exc:
        p.error(str(exc))
    print(json.dumps({"archives_found": len(records), "written": not args.dry_run,
                      "integrity_verified": 0, "restores_verified": 0}))

if __name__ == "__main__":
    main()
