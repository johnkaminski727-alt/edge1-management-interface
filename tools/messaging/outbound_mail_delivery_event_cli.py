#!/usr/bin/env python3
"""Validate, apply, and inspect minimized outbound-mail delivery events.

The CLI is offline. It does not expose a listener, contact a provider, inspect
credentials, read message content, or send mail. Synthetic events require an
explicit test-only flag and must never be used with a production database.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import outbound_mail_delivery_events as events


def load_event(path: pathlib.Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise events.DeliveryEventValidationError(f"unable to read delivery event: {exc}") from exc
    if not isinstance(value, dict):
        raise events.DeliveryEventValidationError("delivery event must be a JSON object")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate one delivery event without mutation")
    validate.add_argument("event", type=pathlib.Path)
    validate.add_argument("--allow-synthetic", action="store_true")

    apply = subparsers.add_parser("apply", help="apply one verified delivery event to a local SQLite store")
    apply.add_argument("event", type=pathlib.Path)
    apply.add_argument("--database", type=pathlib.Path, required=True)
    apply.add_argument("--allow-synthetic", action="store_true")

    status = subparsers.add_parser("status", help="read minimized recipient delivery state")
    status.add_argument("recipient_sha256")
    status.add_argument("--database", type=pathlib.Path, required=True)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "validate":
            event = events.validate_event(
                load_event(args.event),
                allow_synthetic=args.allow_synthetic,
            )
            result = {
                "valid": True,
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "recipient_sha256": event["recipient_sha256"],
                "event_sha256": events.event_sha256(event),
                "source_verified": True,
                "raw_recipient_stored": False,
                "raw_payload_stored": False,
                "message_content_stored": False,
            }
        elif args.command == "apply":
            result = events.apply_event(
                args.database,
                load_event(args.event),
                allow_synthetic=args.allow_synthetic,
            ).to_dict()
        else:
            result = events.recipient_state(args.database, args.recipient_sha256)
    except events.DeliveryEventError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
