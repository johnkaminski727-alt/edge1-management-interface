#!/usr/bin/env python3
"""Build canonical WW.CX Communications metadata from the native Relay database.

The Relay SQLite database remains authoritative. This adapter performs read-only
queries, never selects article bodies, hashes author identifiers, validates every
result against ``wwcx.communications-event.v1``, and writes snapshots atomically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

try:
    from . import unified_communications as core
except ImportError:
    import unified_communications as core  # type: ignore[no-redef]


DEFAULT_DATABASE = Path("/var/lib/wwcx-comms/comms.sqlite3")
DEFAULT_OUTPUT = Path("/var/lib/wwcx-communications-workspace/events.jsonl")
INTERNAL_SOURCES = frozenset({"edge1-repository", "wwcx-bootstrap"})
INBOUND_SOURCE_PREFIXES = ("eternal.",)


class RelaySnapshotError(RuntimeError):
    """Raised when authoritative Relay metadata cannot be mapped safely."""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _direction(source_name: str) -> str:
    if source_name in INTERNAL_SOURCES:
        return "internal"
    if source_name.startswith(INBOUND_SOURCE_PREFIXES):
        return "inbound"
    raise RelaySnapshotError(f"unclassified Relay source: {source_name!r}")


def _connect_read_only(database: Path) -> sqlite3.Connection:
    if not database.is_file():
        raise RelaySnapshotError(f"Relay database is unavailable: {database}")
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def build_events(database: Path = DEFAULT_DATABASE) -> list[dict[str, Any]]:
    """Return validated metadata-only events from authoritative Relay records."""

    connection = _connect_read_only(database)
    try:
        article_count = int(connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0])
        ingest_count = int(connection.execute("SELECT COUNT(*) FROM ingest_items").fetchone()[0])
        rows = connection.execute(
            """
            SELECT
                a.id,
                a.group_name,
                a.author,
                a.subject,
                a.created_at_utc,
                i.source_name,
                i.source_item_id
            FROM articles AS a
            JOIN ingest_items AS i
              ON i.article_id = a.id
            ORDER BY a.id
            """
        ).fetchall()
    finally:
        connection.close()

    if len(rows) != article_count:
        raise RelaySnapshotError("not every Relay article has authoritative ingest linkage")
    if len(rows) != ingest_count:
        raise RelaySnapshotError("Relay ingest ledger and article linkage counts differ")

    events: list[dict[str, Any]] = []
    for row in rows:
        article_id = int(row["id"])
        group_name = str(row["group_name"] or "").strip()
        author = str(row["author"] or "").strip()
        subject = str(row["subject"] or "").strip()
        timestamp = str(row["created_at_utc"] or "").strip()
        source_name = str(row["source_name"] or "").strip()
        source_item_id = str(row["source_item_id"] or "").strip()

        if not group_name:
            raise RelaySnapshotError(f"Relay article {article_id} has no newsgroup")
        if not timestamp:
            raise RelaySnapshotError(f"Relay article {article_id} has no timestamp")
        if not source_name:
            raise RelaySnapshotError(f"Relay article {article_id} has no ingest source")
        if not source_item_id:
            raise RelaySnapshotError(f"Relay article {article_id} has no ingest source item ID")

        sender_identity = (
            f"identity:nntp-author-sha256:{_sha256_text(author)}" if author else None
        )
        audit_digest = _sha256_text(source_name + "\0" + source_item_id)

        event = {
            "contract": "wwcx.communications-event.v1",
            "communications_event_id": f"comm_nntp_article_{article_id}",
            "conversation_id": ("nntp-group:" + group_name)[:160],
            "thread_id": None,
            "case_id": None,
            "control_id": None,
            "channel": "nntp",
            "direction": _direction(source_name),
            "timestamp_utc": timestamp,
            "sender_identity_ref": sender_identity,
            "recipient_identity_refs": [("newsgroup:" + group_name)[:200]],
            "native_record": {
                "record_id": f"article:{article_id}",
                "source": "edge1-comms-relay",
                "provider": source_name[:128],
                "record_type": "nntp_article",
            },
            "subject_or_summary": subject[:1000] or None,
            "status": "observed",
            "security": {
                "state": "normal",
                "reason_code": None,
                "quarantine_release_authorized": False,
            },
            "attachment_media_refs": [],
            "correspondence": {"parent_event_id": None, "relation": "none"},
            "derived": {
                "ai_generated": False,
                "derivation_type": None,
                "source_event_ids": [],
            },
            "provenance": {
                "source_channel": "nntp",
                "authoritative_native_record": True,
                "transformations": [
                    "metadata_only",
                    "body_excluded",
                    "author_identity_sha256",
                ],
            },
            "audit_refs": [f"ingest-sha256:{audit_digest}"],
        }
        events.append(core.validate_event(event))

    return core.sort_events(events)


def write_snapshot_atomic(events: Iterable[dict[str, Any]], output: Path) -> int:
    """Validate and atomically replace one canonical JSONL snapshot."""

    validated = core.sort_events(events)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            for event in validated:
                temporary.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_name, 0o640)
        os.replace(temporary_name, output)
        temporary_name = None
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
    return len(validated)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    events = build_events(args.database)
    count = write_snapshot_atomic(events, args.output)
    internal = sum(item["direction"] == "internal" for item in events)
    inbound = sum(item["direction"] == "inbound" for item in events)

    print(f"snapshot_events={count}")
    print(f"internal_events={internal}")
    print(f"inbound_events={inbound}")
    print("raw_body_fields=0")
    print("canonical_validation=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
