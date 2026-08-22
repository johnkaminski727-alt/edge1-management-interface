#!/usr/bin/env python3
"""Cookie Monster Alpha read-only media ingestion foundation.

The source tree is immutable input. Generated state is written to a separate
output directory. Provenance and audit logs are append-only across runs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable

PIPELINE_STAGES = ("ingest", "normalize", "extract", "analyze", "knowledge-synthesize")
DEFAULT_ACTOR = "cookie-monster-alpha"
SCHEMA_VERSION = "wwcx.cookie-monster.alpha.v1"
EXTRACTION_METHOD = "cookie-monster-alpha-metadata"
DEFAULT_METADATA_BUDGET_SECONDS = 20.0
DEFAULT_RUN_BUDGET_SECONDS = 300.0


class AlphaBoundaryError(RuntimeError):
    """Raised when an Alpha safety boundary would be crossed."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def validate_paths(source: Path, output: Path) -> tuple[Path, Path]:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    if not source.is_dir():
        raise AlphaBoundaryError(f"source must be an existing directory: {source}")
    if source == output or is_within(output, source):
        raise AlphaBoundaryError("output must be outside the source tree; Alpha never writes into source data")
    return source, output


def discover_files(root: Path, max_files: int | None = None) -> list[Path]:
    """Discover regular files without following any symlink outside the source."""
    root = root.resolve()
    rows: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(dirpath)
        safe_dirs: list[str] = []
        for name in sorted(dirnames):
            candidate = current / name
            if candidate.is_symlink():
                raise AlphaBoundaryError(f"symlink directory rejected in staging source: {candidate.relative_to(root)}")
            resolved = candidate.resolve()
            if not is_within(resolved, root):
                raise AlphaBoundaryError(f"directory escapes staging source: {candidate.relative_to(root)}")
            safe_dirs.append(name)
        dirnames[:] = safe_dirs
        for name in sorted(filenames):
            candidate = current / name
            if candidate.is_symlink():
                raise AlphaBoundaryError(f"symlink file rejected in staging source: {candidate.relative_to(root)}")
            resolved = candidate.resolve()
            if not is_within(resolved, root):
                raise AlphaBoundaryError(f"file escapes staging source: {candidate.relative_to(root)}")
            if not resolved.is_file():
                continue
            rows.append(resolved)
            if max_files is not None and len(rows) >= max_files:
                return sorted(rows, key=lambda p: p.relative_to(root).as_posix())
    return sorted(rows, key=lambda p: p.relative_to(root).as_posix())


def _tool_path(name: str) -> str | None:
    return shutil.which(name)


def tooling_status() -> dict[str, Any]:
    names = ("ffprobe", "mediainfo", "exiftool")
    return {name: {"available": bool(_tool_path(name)), "path": _tool_path(name)} for name in names}


def _run_json(command: list[str], timeout: float = 20.0) -> tuple[Any | None, str | None]:
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=max(0.1, timeout),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"exit={completed.returncode}"
        return None, detail[:1000]
    try:
        return json.loads(completed.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"invalid-json: {exc}"


def extract_metadata(path: Path, budget_seconds: float = DEFAULT_METADATA_BUDGET_SECONDS) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Run optional metadata tools within one aggregate per-file time budget."""
    metadata: dict[str, Any] = {}
    diagnostics: list[dict[str, str]] = []
    deadline = time.monotonic() + max(0.0, budget_seconds)
    specs = (
        ("ffprobe", lambda tool: [tool, "-v", "error", "-show_format", "-show_streams", "-of", "json", "--", str(path)]),
        ("mediainfo", lambda tool: [tool, "--Output=JSON", "--", str(path)]),
        ("exiftool", lambda tool: [tool, "-j", "-n", "--", str(path)]),
    )
    for name, command_builder in specs:
        tool = _tool_path(name)
        if not tool:
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            diagnostics.append({"tool": "budget", "error": f"metadata time budget exhausted before {name}"})
            break
        value, error = _run_json(command_builder(tool), timeout=remaining)
        if value is not None:
            metadata[name] = value
        elif error:
            diagnostics.append({"tool": name, "error": error})
    return metadata, diagnostics


def analyze_asset(
    path: Path,
    root: Path,
    actor: str,
    actor_version: str,
    metadata_budget_seconds: float = DEFAULT_METADATA_BUDGET_SECONDS,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    relative = path.relative_to(root).as_posix()
    started = utc_now()
    digest, size = sha256_file(path)
    stat = path.stat()
    guessed_mime, guessed_encoding = mimetypes.guess_type(path.name)
    metadata, diagnostics = extract_metadata(path, budget_seconds=metadata_budget_seconds)
    asset_id = f"sha256:{digest}"
    audit = [{"timestamp": started, "event": "source.read", "source_asset_id": asset_id, "source_asset_location": relative, "actor": actor, "bytes_read": size, "result": "ok"}]
    for diagnostic in diagnostics:
        audit.append({"timestamp": utc_now(), "event": "metadata.diagnostic", "source_asset_id": asset_id, "source_asset_location": relative, "actor": actor, "result": "review", **diagnostic})
    return {
        "source_asset_id": asset_id,
        "source_asset_location": relative,
        "filename": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": size,
        "mtime_ns": stat.st_mtime_ns,
        "mime_type": guessed_mime or "application/octet-stream",
        "encoding": guessed_encoding,
        "ingestion_timestamp": started,
        "ingestion_actor": actor,
        "ingestion_actor_version": actor_version,
        "metadata": metadata,
        "diagnostics": diagnostics,
    }, audit


def duplicate_groups(assets: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for asset in assets:
        grouped.setdefault(asset["source_asset_id"], []).append(asset)
    result = []
    for source_asset_id, rows in sorted(grouped.items()):
        if len(rows) < 2:
            continue
        result.append({"source_asset_id": source_asset_id, "count": len(rows), "locations": [row["source_asset_location"] for row in rows]})
    return result


def _record_facts(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "filename": asset["filename"],
        "extension": asset["extension"],
        "size_bytes": asset["size_bytes"],
        "mime_type": asset["mime_type"],
    }


def record_idempotency_key_from_parts(
    source_asset_id: str,
    source_asset_location: str,
    extraction_method: str,
    extraction_method_version: str,
    facts: dict[str, Any],
) -> str:
    payload = {
        "source_asset_id": source_asset_id,
        "source_asset_location": source_asset_location,
        "extraction_method": extraction_method,
        "extraction_method_version": extraction_method_version,
        "facts": facts,
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def record_idempotency_key(record: dict[str, Any]) -> str | None:
    value = record.get("idempotency_key")
    if isinstance(value, str) and value:
        return value
    required = ("source_asset_id", "source_asset_location", "extraction_method", "extraction_method_version", "facts")
    if not all(key in record for key in required):
        return None
    return record_idempotency_key_from_parts(
        record["source_asset_id"],
        record["source_asset_location"],
        record["extraction_method"],
        record["extraction_method_version"],
        record["facts"],
    )


def make_knowledge_records(
    assets: Iterable[dict[str, Any]],
    actor_version: str,
    existing_records: Iterable[dict[str, Any]] = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    existing_list = list(existing_records)
    existing_by_key: dict[str, dict[str, Any]] = {}
    for record in existing_list:
        key = record_idempotency_key(record)
        if key:
            existing_by_key[key] = record
    previous_hash = next((row.get("record_hash") for row in reversed(existing_list) if row.get("record_hash")), None)
    current_records: list[dict[str, Any]] = []
    new_records: list[dict[str, Any]] = []
    for asset in assets:
        facts = _record_facts(asset)
        key = record_idempotency_key_from_parts(
            asset["source_asset_id"], asset["source_asset_location"], EXTRACTION_METHOD, actor_version, facts
        )
        existing = existing_by_key.get(key)
        if existing is not None:
            current_records.append(existing)
            continue
        deterministic_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        body = {
            "schema": SCHEMA_VERSION,
            "knowledge_record_id": f"kr-{deterministic_id}",
            "idempotency_key": key,
            "source_asset_id": asset["source_asset_id"],
            "source_asset_location": asset["source_asset_location"],
            "ingestion_timestamp": asset["ingestion_timestamp"],
            "ingestion_actor": asset["ingestion_actor"],
            "ingestion_actor_version": asset["ingestion_actor_version"],
            "extraction_method": EXTRACTION_METHOD,
            "extraction_method_version": actor_version,
            "derivation_chain": [],
            "confidence": 1.0 if not asset["diagnostics"] else 0.7,
            "review_status": "pending_review" if asset["diagnostics"] else "draft",
            "supersedes": None,
            "superseded_by": None,
            "correction_reason": None,
            "previous_record_hash": previous_hash,
            "facts": facts,
        }
        record_hash = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
        body["record_hash"] = f"sha256:{record_hash}"
        current_records.append(body)
        new_records.append(body)
        existing_by_key[key] = body
        previous_hash = body["record_hash"]
    return current_records, new_records


def build_snapshot(
    source: Path,
    actor: str = DEFAULT_ACTOR,
    actor_version: str = "0.1.0-alpha",
    max_files: int | None = None,
    existing_records: Iterable[dict[str, Any]] = (),
    metadata_budget_seconds: float = DEFAULT_METADATA_BUDGET_SECONDS,
    run_time_budget_seconds: float = DEFAULT_RUN_BUDGET_SECONDS,
) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    started_monotonic = time.monotonic()
    run_id = "run-" + hashlib.sha256(f"{utc_now()}:{os.getpid()}:{time.time_ns()}".encode("utf-8")).hexdigest()[:24]
    for path in discover_files(source, max_files=max_files):
        elapsed = time.monotonic() - started_monotonic
        if elapsed >= max(0.0, run_time_budget_seconds):
            raise AlphaBoundaryError(f"run time budget exceeded after {elapsed:.3f}s")
        asset, events = analyze_asset(
            path,
            source,
            actor,
            actor_version,
            metadata_budget_seconds=metadata_budget_seconds,
        )
        for event in events:
            event["run_id"] = run_id
        assets.append(asset)
        audit.extend(events)
    duplicates = duplicate_groups(assets)
    records, new_records = make_knowledge_records(assets, actor_version, existing_records=existing_records)
    new_ids = {row["knowledge_record_id"] for row in new_records}
    for record in records:
        if record["knowledge_record_id"] not in new_ids:
            audit.append({
                "timestamp": utc_now(),
                "event": "knowledge_record.reused",
                "run_id": run_id,
                "knowledge_record_id": record["knowledge_record_id"],
                "source_asset_id": record["source_asset_id"],
                "source_asset_location": record["source_asset_location"],
                "actor": actor,
                "result": "idempotent-hit",
            })
    review_queue = [{"knowledge_record_id": record["knowledge_record_id"], "source_asset_id": record["source_asset_id"], "source_asset_location": record["source_asset_location"], "review_status": record["review_status"], "reason": "metadata_tool_diagnostic" if record["review_status"] == "pending_review" else "initial_alpha_record"} for record in records if record["review_status"] in {"draft", "pending_review"}]
    unique_assets = len({asset["source_asset_id"] for asset in assets})
    return {
        "schema": SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": utc_now(),
        "mode": "alpha-read-only",
        "source_kind": "staging",
        "pipeline_stages": list(PIPELINE_STAGES),
        "summary": {
            "files_discovered": len(assets),
            "unique_assets": unique_assets,
            "duplicate_groups": len(duplicates),
            "knowledge_records": len(records),
            "new_knowledge_records": len(new_records),
            "reused_knowledge_records": len(records) - len(new_records),
            "review_items": len(review_queue),
            "unauthorized_source_writes": 0,
        },
        "tooling": tooling_status(),
        "budgets": {"metadata_per_file_seconds": metadata_budget_seconds, "run_seconds": run_time_budget_seconds},
        "fengus": {"connected": False, "mode": "not-connected-in-m0-m1", "jobs_active": 0, "jobs_completed": 0, "jobs_failed": 0},
        "assets": assets,
        "duplicates": duplicates,
        "knowledge_records": records,
        "new_knowledge_records": new_records,
        "review_queue": review_queue,
        "audit": audit,
    }


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(canonical_json(row) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AlphaBoundaryError(f"invalid append-only JSONL at {path}:{line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise AlphaBoundaryError(f"invalid append-only JSONL object at {path}:{line_number}")
            rows.append(value)
    return rows


def write_snapshot(snapshot: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    atomic_text(output / "status.json", json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    append_jsonl(output / "knowledge-records.jsonl", snapshot.get("new_knowledge_records", snapshot["knowledge_records"]))
    append_jsonl(output / "audit.jsonl", snapshot["audit"])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cookie Monster Alpha read-only media ingestion")
    parser.add_argument("--source", required=True, type=Path, help="staging source directory (read only)")
    parser.add_argument("--output", required=True, type=Path, help="separate generated evidence/status directory")
    parser.add_argument("--actor", default=DEFAULT_ACTOR)
    parser.add_argument("--actor-version", default="0.1.0-alpha")
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument("--metadata-budget-seconds", type=float, default=DEFAULT_METADATA_BUDGET_SECONDS)
    parser.add_argument("--run-time-budget-seconds", type=float, default=DEFAULT_RUN_BUDGET_SECONDS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        source, output = validate_paths(args.source, args.output)
        existing_records = read_jsonl(output / "knowledge-records.jsonl")
        snapshot = build_snapshot(
            source,
            actor=args.actor,
            actor_version=args.actor_version,
            max_files=args.max_files,
            existing_records=existing_records,
            metadata_budget_seconds=args.metadata_budget_seconds,
            run_time_budget_seconds=args.run_time_budget_seconds,
        )
        write_snapshot(snapshot, output)
    except AlphaBoundaryError as exc:
        print(f"cookie-monster-alpha: boundary error: {exc}", file=sys.stderr)
        return 2
    print(canonical_json({"status": "ok", "source": str(source), "output": str(output), "summary": snapshot["summary"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
