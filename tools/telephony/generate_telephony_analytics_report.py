#!/usr/bin/env python3
"""Generate a new owner-only telephony aggregate report bundle offline."""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from telephony_aggregate_report import (  # noqa: E402
    MAX_INPUT_BYTES,
    AggregateReportError,
    build_report,
    canonical_json,
    input_manifest_sha256,
    normalize_report_input,
    write_report_bundle,
)


def read_input(path: Path) -> dict[str, Any]:
    if not path.is_absolute():
        raise AggregateReportError("input path must be absolute")
    if path.is_symlink():
        raise AggregateReportError("input path must not be a symlink")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise AggregateReportError(f"could not open input: {exc}") from exc
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise AggregateReportError("input must be a regular file")
        if metadata.st_size > MAX_INPUT_BYTES:
            raise AggregateReportError("input exceeds the accepted size limit")
        chunks: list[bytes] = []
        remaining = metadata.st_size + 1
        while remaining > 0:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        if sum(len(chunk) for chunk in chunks) > MAX_INPUT_BYTES:
            raise AggregateReportError("input exceeds the accepted size limit")
    finally:
        os.close(fd)
    try:
        value = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AggregateReportError("input must be one UTF-8 JSON document") from exc
    if not isinstance(value, dict):
        raise AggregateReportError("input JSON must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an offline aggregate telephony report bundle without live source access."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate and summarize the input without creating output files",
    )
    args = parser.parse_args()

    try:
        normalized = normalize_report_input(read_input(args.input))
        manifest_hash = input_manifest_sha256(normalized)
        report = build_report(normalized)
        if args.validate_only:
            result = {
                "status": "valid",
                "report_id": report["report_id"],
                "report_kind": report["report_kind"],
                "input_manifest_sha256": manifest_hash,
                "output_created": False,
                "audit_event_appended": False,
            }
        else:
            result = write_report_bundle(args.output_dir, report, manifest_hash)
            result["status"] = "generated"
    except AggregateReportError as exc:
        parser.error(str(exc))

    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
