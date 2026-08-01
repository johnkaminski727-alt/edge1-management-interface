#!/usr/bin/env python3
"""Append or verify privacy-minimized telephony analytics report audit events."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "server"))

from telephony_report_audit import (  # noqa: E402
    ReportAuditError,
    append_audit_event,
    verify_audit_log,
)


def load_event(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportAuditError(f"could not read event file: {exc}") from exc
    if not isinstance(value, dict):
        raise ReportAuditError("event file must contain one JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Append or verify a hash-chained telephony analytics report audit log."
    )
    parser.add_argument("--audit-log", required=True, type=Path)
    parser.add_argument("--event-file", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if args.verify_only == (args.event_file is not None):
        parser.error("choose exactly one of --verify-only or --event-file")

    try:
        if args.verify_only:
            result = verify_audit_log(args.audit_log)
            print(json.dumps(result, sort_keys=True))
        else:
            event = append_audit_event(args.audit_log, load_event(args.event_file))
            print(json.dumps({
                "appended": True,
                "event_id": event["event_id"],
                "event_sha256": event["event_sha256"],
                "previous_event_sha256": event["previous_event_sha256"],
            }, sort_keys=True))
    except ReportAuditError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
