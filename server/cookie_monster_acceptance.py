#!/usr/bin/env python3
"""Cookie Monster Alpha M6 synthetic acceptance harness.

The harness creates its own deterministic non-production staging dataset, runs
Cookie Monster twice, exercises human-review and Fengus boundaries, and emits a
machine-readable acceptance report. It never needs a canonical archive path or
credential.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
from typing import Any
import wave

import cookie_monster_alpha as alpha
import cookie_monster_contract as contract
import cookie_monster_fengus_worker as fengus
import cookie_monster_review as review

SCHEMA = "wwcx.cookie-monster.acceptance.v1"
DATASET = "synthetic-media-v1"
ACTOR = "cookie-monster-m6-acceptance"
ACTOR_VERSION = "m6-synthetic-v1"
REVIEW_LATENCY_BOUND_MS = 5000.0


class AcceptanceError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _write_tone(path: Path, seconds: float = 0.08, rate: int = 8000, frequency: float = 440.0) -> None:
    frames = int(seconds * rate)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        for index in range(frames):
            sample = int(7000 * math.sin(2.0 * math.pi * frequency * index / rate))
            handle.writeframesraw(struct.pack("<h", sample))


def prepare_synthetic_source(source: Path) -> None:
    if source.exists() and any(source.iterdir()):
        raise AcceptanceError("synthetic staging directory must be empty; refusing to overwrite existing data")
    source.mkdir(parents=True, exist_ok=True)
    phrase = "Cookie Monster eats ASCII for brunch.\n"
    (source / "ascii-brunch.txt").write_text(phrase, encoding="utf-8")
    (source / "ascii-brunch-copy.txt").write_text(phrase, encoding="utf-8")
    (source / "facts.json").write_text(json.dumps({"mascot": "cookie-monster", "mode": "alpha", "source": "synthetic"}, sort_keys=True) + "\n", encoding="utf-8")
    (source / "blob.bin").write_bytes(bytes(range(64)))
    _write_tone(source / "tone.wav")


def source_state(source: Path) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for path in sorted(p for p in source.rglob("*") if p.is_file()):
        digest, size = alpha.sha256_file(path)
        state[path.relative_to(source).as_posix()] = {
            "sha256": digest,
            "size": size,
            "mtime_ns": path.stat().st_mtime_ns,
        }
    return state


def verify_provenance(records: list[dict[str, Any]], source: Path) -> list[str]:
    gaps: list[str] = []
    for record in records:
        location = record.get("source_asset_location")
        if not isinstance(location, str):
            gaps.append(f"{record.get('knowledge_record_id')}: missing source_asset_location")
            continue
        path = source / location
        if not path.is_file():
            gaps.append(f"{record.get('knowledge_record_id')}: source location missing")
            continue
        digest, _ = alpha.sha256_file(path)
        if record.get("source_asset_id") != f"sha256:{digest}":
            gaps.append(f"{record.get('knowledge_record_id')}: source hash mismatch")
    return gaps


def verify_record_chain(records: list[dict[str, Any]]) -> list[str]:
    gaps: list[str] = []
    previous: str | None = None
    for record in records:
        record_id = str(record.get("knowledge_record_id"))
        if record.get("previous_record_hash") != previous:
            gaps.append(f"{record_id}: previous_record_hash mismatch")
        body = {key: value for key, value in record.items() if key != "record_hash"}
        expected = "sha256:" + hashlib.sha256(alpha.canonical_json(body).encode("utf-8")).hexdigest()
        if record.get("record_hash") != expected:
            gaps.append(f"{record_id}: record_hash mismatch")
        previous = record.get("record_hash")
    return gaps


def verify_review_chain(decisions: list[dict[str, Any]]) -> list[str]:
    gaps: list[str] = []
    previous: str | None = None
    for event in decisions:
        event_id = str(event.get("event_id"))
        if event.get("previous_decision_hash") != previous:
            gaps.append(f"{event_id}: previous_decision_hash mismatch")
        body = {key: value for key, value in event.items() if key != "decision_hash"}
        expected = "sha256:" + hashlib.sha256(review.canonical_json(body).encode("utf-8")).hexdigest()
        if event.get("decision_hash") != expected:
            gaps.append(f"{event_id}: decision_hash mismatch")
        previous = event.get("decision_hash")
    return gaps


def _criterion(value: Any, passed: bool, detail: str = "") -> dict[str, Any]:
    return {"value": value, "pass": bool(passed), "detail": detail}


def run_acceptance(workspace: Path) -> dict[str, Any]:
    workspace = workspace.resolve()
    source = workspace / "synthetic-staging"
    output = workspace / "generated"
    prepare_synthetic_source(source)
    before = source_state(source)

    job = contract.make_request(
        DATASET,
        "bigbird-cookie-monster-acceptance",
        max_files=50,
        metadata_budget_seconds=0.5,
        run_budget_seconds=30.0,
    )

    first = alpha.build_snapshot(
        source,
        actor=ACTOR,
        actor_version=ACTOR_VERSION,
        max_files=50,
        metadata_budget_seconds=0.5,
        run_time_budget_seconds=30.0,
    )
    alpha.write_snapshot(first, output)
    after_first = source_state(source)
    first_record_bytes = (output / "knowledge-records.jsonl").read_bytes()
    first_audit_bytes = (output / "audit.jsonl").read_bytes()

    existing = alpha.read_jsonl(output / "knowledge-records.jsonl")
    second = alpha.build_snapshot(
        source,
        actor=ACTOR,
        actor_version=ACTOR_VERSION,
        max_files=50,
        existing_records=existing,
        metadata_budget_seconds=0.5,
        run_time_budget_seconds=30.0,
    )
    alpha.write_snapshot(second, output)
    after_second = source_state(source)
    second_record_bytes = (output / "knowledge-records.jsonl").read_bytes()
    second_audit_bytes = (output / "audit.jsonl").read_bytes()
    records = alpha.read_jsonl(output / "knowledge-records.jsonl")

    provenance_gaps = verify_provenance(records, source)
    chain_gaps = verify_record_chain(records)

    decisions: list[dict[str, Any]] = []
    target = records[0]
    review_started = time.monotonic()
    current = target.get("review_status")
    if current == "draft":
        event = review.make_decision(records, decisions, target["knowledge_record_id"], "pending_review", ACTOR, "M6 synthetic acceptance submission")
        review.append_event(output / "review-decisions.jsonl", event)
        decisions.append(event)
        current = "pending_review"
    if current == "pending_review":
        event = review.make_decision(records, decisions, target["knowledge_record_id"], "approved", ACTOR, "M6 synthetic provenance verified")
        review.append_event(output / "review-decisions.jsonl", event)
        decisions.append(event)
    review_latency_ms = (time.monotonic() - review_started) * 1000.0
    review_state = review.build_review_snapshot(records, decisions)
    review_chain_gaps = verify_review_chain(decisions)
    review.atomic_json(output / "review-state.json", review_state)

    work_id = "work-" + hashlib.sha256(target["source_asset_id"].encode("utf-8")).hexdigest()[:24]
    work_request = {
        "schema": fengus.SCHEMA,
        "job_id": job["job_id"],
        "work_id": work_id,
        "operation": "text.token-stats",
        "source_asset_id": target["source_asset_id"],
        "payload": {"text": "Cookie Monster eats ASCII for brunch.\n"},
    }
    worker_result = fengus.execute(work_request)
    direct_archive_blocked = False
    forbidden = dict(work_request)
    forbidden["payload"] = {"archive": "/srv/cookie-monster/canonical", "text": "nope"}
    try:
        fengus.execute(forbidden)
    except fengus.WorkerError:
        direct_archive_blocked = True
    outside_allowlist_blocked = False
    forbidden_operation = dict(work_request)
    forbidden_operation["operation"] = "shell.exec"
    try:
        fengus.execute(forbidden_operation)
    except fengus.WorkerError:
        outside_allowlist_blocked = True

    audit_rows = alpha.read_jsonl(output / "audit.jsonl")
    source_read_events = [row for row in audit_rows if row.get("event") == "source.read"]
    source_read_run_ids = {row.get("run_id") for row in source_read_events if row.get("run_id")}

    job_status = {"schema": "wwcx.cookie-monster.job-status.v1", "generated_at": alpha.utc_now(), "job": job, "state": "synthetic-acceptance-completed"}
    alpha.atomic_text(output / "job-status.json", json.dumps(job_status, indent=2, sort_keys=True) + "\n")

    criteria = {
        "assets_ingested": _criterion(len(records), len(records) == len(before), f"expected {len(before)} records including duplicate locations"),
        "duplicate_detection": _criterion(first["summary"]["duplicate_groups"], first["summary"]["duplicate_groups"] >= 1),
        "zero_source_mutation": _criterion(before == after_first == after_second, before == after_first == after_second),
        "zero_unauthorized_source_writes": _criterion(second["summary"]["unauthorized_source_writes"], second["summary"]["unauthorized_source_writes"] == 0),
        "zero_provenance_gaps": _criterion(len(provenance_gaps), not provenance_gaps, "; ".join(provenance_gaps)),
        "zero_record_chain_gaps": _criterion(len(chain_gaps), not chain_gaps, "; ".join(chain_gaps)),
        "repeat_run_idempotent": _criterion(second["summary"]["new_knowledge_records"], second_record_bytes == first_record_bytes and second["summary"]["new_knowledge_records"] == 0),
        "audit_append_only": _criterion(len(second_audit_bytes), second_audit_bytes.startswith(first_audit_bytes) and len(second_audit_bytes) > len(first_audit_bytes)),
        "review_transition": _criterion(review_state["summary"].get("approved", 0), review_state["summary"].get("approved", 0) >= 1),
        "zero_review_chain_gaps": _criterion(len(review_chain_gaps), not review_chain_gaps, "; ".join(review_chain_gaps)),
        "review_latency_bound_ms": _criterion(round(review_latency_ms, 3), review_latency_ms <= REVIEW_LATENCY_BOUND_MS, f"bound={REVIEW_LATENCY_BOUND_MS:.0f}ms"),
        "fengus_allowlisted_job": _criterion(worker_result.get("operation"), worker_result.get("operation") == "text.token-stats"),
        "fengus_direct_archive_access_blocked": _criterion(direct_archive_blocked, direct_archive_blocked),
        "fengus_jobs_outside_allowlist": _criterion(0 if outside_allowlist_blocked else 1, outside_allowlist_blocked),
        "audit_read_coverage": _criterion(
            len(source_read_events),
            len(source_read_events) == len(before) * 2 and len(source_read_run_ids) == 2,
            f"expected {len(before) * 2} source.read events across 2 runs",
        ),
        "bigbird_job_contract_path_free": _criterion(job["dataset"], "/" not in canonical_json(job) and "http" not in canonical_json(job).lower()),
    }
    passed = all(item["pass"] for item in criteria.values())
    report = {
        "schema": SCHEMA,
        "generated_at": alpha.utc_now(),
        "dataset": DATASET,
        "mode": "synthetic-non-production",
        "result": "pass" if passed else "fail",
        "summary": {
            "assets": len(records),
            "unique_assets": second["summary"]["unique_assets"],
            "duplicate_groups": second["summary"]["duplicate_groups"],
            "provenance_gaps": len(provenance_gaps) + len(chain_gaps) + len(review_chain_gaps),
            "unauthorized_source_writes": second["summary"]["unauthorized_source_writes"],
            "fengus_jobs_outside_allowlist": 0 if outside_allowlist_blocked else 1,
            "review_latency_ms": round(review_latency_ms, 3),
        },
        "criteria": criteria,
    }
    alpha.atomic_text(output / "acceptance.json", json.dumps(report, indent=2, sort_keys=True) + "\n")
    if not passed:
        failed = ", ".join(name for name, value in criteria.items() if not value["pass"])
        raise AcceptanceError(f"M6 synthetic acceptance failed: {failed}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cookie Monster Alpha M6 synthetic acceptance")
    parser.add_argument("--workspace", type=Path, help="empty workspace to retain generated acceptance evidence")
    args = parser.parse_args(argv)
    try:
        if args.workspace:
            args.workspace.mkdir(parents=True, exist_ok=True)
            report = run_acceptance(args.workspace)
        else:
            with tempfile.TemporaryDirectory(prefix="cookie-monster-m6-") as td:
                report = run_acceptance(Path(td))
    except (AcceptanceError, alpha.AlphaBoundaryError, review.ReviewError, fengus.WorkerError, contract.ContractError, OSError) as exc:
        print(f"cookie-monster-acceptance: {exc}", file=sys.stderr)
        return 2
    print(canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
