#!/usr/bin/env python3
"""Export a privacy-limited VPN registration summary for Operations Center."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

try:
    from vpn_access_registration import RegistrationStore
except ModuleNotFoundError:
    from server.vpn_access_registration import RegistrationStore


DEFAULT_DB = Path(os.environ.get("EDGE1_OPS_DB", "/var/lib/edge1-operations-api/audit.sqlite3"))
DEFAULT_OUTPUT = Path("/var/www/edge1-status/vpn-access-registration.json")


def export_payload(store: RegistrationStore) -> dict[str, object]:
    summary = store.summary()
    recent_events = store.audit_events(limit=10)
    return {
        **summary,
        "recent_events": [
            {
                "created_at": event["created_at"],
                "event_type": event["event_type"],
            }
            for event in recent_events
        ],
    }


def write_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    write_atomic(args.output, export_payload(RegistrationStore(args.db)))


if __name__ == "__main__":
    main()
