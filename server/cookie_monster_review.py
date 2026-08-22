#!/usr/bin/env python3
"""Append-only human review state for Cookie Monster Alpha knowledge records."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Iterable

SCHEMA = "wwcx.cookie-monster.review.v1"
ACTOR_RE = re.compile(r"^[A-Za-z0-9._@:-]{1,80}$")
RECORD_RE = re.compile(r"^kr-[a-f0-9]{16,64}$")
ALLOWED_TRANSITIONS = {
    "draft": {"pending_review"},
    "pending_review": {"approved", "rejected"},
    "approved": set(),
    "rejected": set(),
}


class ReviewError(ValueError):
    pass


def utc_now() -> str:
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReviewError(f"invalid JSONL at {path}:{number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ReviewError(f"invalid JSONL object at {path}:{number}")
        rows.append(value)
    return rows


def knowledge_index(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for record in records:
        record_id = record.get("knowledge_record_id")
        if isinstance(record_id, str):
            result[record_id] = record
    return result


def current_states(records: Iterable[dict[str, Any]], decisions: Iterable[dict[str, Any]]) -> dict[str, str]:
    records = list(records)
    known = knowledge_index(records)
    states = {record_id: str(row.get("review_status", "draft")) for record_id, row in known.items()}
    for event in decisions:
        record_id = event.get("knowledge_record_id")
        if record_id not in known:
            raise ReviewError(f"review event references unknown record: {record_id}")
        from_state = event.get("from_status")
        to_state = event.get("to_status")
        if states[record_id] != from_state:
            raise ReviewError(f"review history state mismatch for {record_id}")
        if to_state not in ALLOWED_TRANSITIONS.get(from_state, set()):
            raise ReviewError(f"invalid historical transition {from_state}->{to_state}")
        states[record_id] = to_state
    return states


def previous_decision_hash(decisions: Iterable[dict[str, Any]]) -> str | None:
    rows = list(decisions)
    return next((row.get("decision_hash") for row in reversed(rows) if row.get("decision_hash")), None)


def make_decision(
    records: Iterable[dict[str, Any]],
    decisions: Iterable[dict[str, Any]],
    record_id: str,
    to_status: str,
    actor: str,
    reason: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    record_list = list(records)
    decision_list = list(decisions)
    if not RECORD_RE.fullmatch(record_id):
        raise ReviewError("invalid knowledge_record_id")
    if not ACTOR_RE.fullmatch(actor or ""):
        raise ReviewError("invalid review actor")
    reason = (reason or "").strip()
    if not 3 <= len(reason) <= 500:
        raise ReviewError("review reason must contain 3 to 500 characters")
    known = knowledge_index(record_list)
    if record_id not in known:
        raise ReviewError("knowledge record not found")
    states = current_states(record_list, decision_list)
    from_status = states[record_id]
    if to_status not in ALLOWED_TRANSITIONS.get(from_status, set()):
        raise ReviewError(f"transition {from_status}->{to_status} is not allowed")
    body = {
        "schema": SCHEMA,
        "timestamp": timestamp or utc_now(),
        "knowledge_record_id": record_id,
        "source_asset_id": known[record_id].get("source_asset_id"),
        "from_status": from_status,
        "to_status": to_status,
        "actor": actor,
        "reason": reason,
        "previous_decision_hash": previous_decision_hash(decision_list),
    }
    body["event_id"] = "review-" + hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()[:24]
    body["decision_hash"] = "sha256:" + hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    return body


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (canonical_json(event) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o640)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)


def build_review_snapshot(records: Iterable[dict[str, Any]], decisions: Iterable[dict[str, Any]]) -> dict[str, Any]:
    record_list = list(records)
    decision_list = list(decisions)
    states = current_states(record_list, decision_list)
    by_id = knowledge_index(record_list)
    rows = []
    counts = {name: 0 for name in ALLOWED_TRANSITIONS}
    for record_id in sorted(states):
        state = states[record_id]
        counts[state] = counts.get(state, 0) + 1
        record = by_id[record_id]
        rows.append({
            "knowledge_record_id": record_id,
            "source_asset_id": record.get("source_asset_id"),
            "source_asset_location": record.get("source_asset_location"),
            "review_status": state,
            "allowed_next": sorted(ALLOWED_TRANSITIONS.get(state, set())),
        })
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "summary": counts,
        "records": rows,
        "decision_events": len(decision_list),
        "approval_owner": "human-operator",
        "mutation_transport": "alpha-cli-only",
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def load_output(output: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = read_jsonl(output / "knowledge-records.jsonl")
    decisions = read_jsonl(output / "review-decisions.jsonl")
    if not records:
        raise ReviewError("no knowledge records are available for review")
    return records, decisions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cookie Monster Alpha review queue")
    parser.add_argument("--output", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    decide = sub.add_parser("decide")
    decide.add_argument("--record", required=True)
    decide.add_argument("--to", required=True, choices=["pending_review", "approved", "rejected"])
    decide.add_argument("--actor", required=True)
    decide.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    try:
        records, decisions = load_output(args.output)
        if args.command == "decide":
            event = make_decision(records, decisions, args.record, args.to, args.actor, args.reason)
            append_event(args.output / "review-decisions.jsonl", event)
            decisions.append(event)
        snapshot = build_review_snapshot(records, decisions)
        atomic_json(args.output / "review-state.json", snapshot)
    except (ReviewError, OSError) as exc:
        print(f"cookie-monster-review: {exc}", file=sys.stderr)
        return 2
    print(canonical_json(snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
