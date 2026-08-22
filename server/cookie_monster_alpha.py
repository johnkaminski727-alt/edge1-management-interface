#!/usr/bin/env python3
"""Cookie Monster Alpha read-only media ingestion foundation.

The source tree is treated as immutable input. All generated state is written to
an explicitly separate output directory. External metadata tools are optional;
failures are recorded as reviewable diagnostics rather than changing source data.
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
from typing import Any, Iterable
import uuid

PIPELINE_STAGES = ("ingest", "normalize", "extract", "analyze", "knowledge-synthesize")
DEFAULT_ACTOR = "cookie-monster-alpha"
SCHEMA_VERSION = "wwcx.cookie-monster.alpha.v1"


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
    rows: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rows.append(path)
        if max_files is not None and len(rows) >= max_files:
            break
    return rows


def _tool_path(name: str) -> str | None:
    return shutil.which(name)


def tooling_status() -> dict[str, Any]:
    names = ("ffprobe", "mediainfo", "exiftool")
    return {name: {"available": bool(_tool_path(name)), "path": _tool_path(name)} for name in names}


def _run_json(command: list[str], timeout: int = 20) -> tuple[Any | None, str | None]:
    try:
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"exit={completed.returncode}"
        return None, detail[:1000]
    try:
        return json.loads(completed.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"invalid-json: {exc}"


def extract_metadata(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Run optional metadata tools using fixed read-only argument shapes."""
    metadata: dict[str, Any] = {}
    diagnostics: list[dict[str, str]] = []

    ffprobe = _tool_path("ffprobe")
    if ffprobe:
        value, error = _run_json([ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", "--", str(path)])
        if value is not None:
            metadata["ffprobe"] = value
        elif error:
            diagnostics.append({"tool": "ffprobe", "error": error})

    mediainfo = _tool_path("mediainfo")
    if mediainfo:
        value, error = _run_json([mediainfo, "--Output=JSON", "--", str(path)])
        if value is not None:
            metadata["mediainfo"] = value
        elif error:
            diagnostics.append({"tool": "mediainfo", "error": error})

    exiftool = _tool_path("exiftool")
    if exiftool:
        value, error = _run_json([exiftool, "-j", "-n", "--", str(path)])
        if value is not None:
            metadata["exiftool"] = value
        elif error:
            diagnostics.append({"tool": "exiftool", "error": error})
    return metadata, diagnostics


def analyze_asset(path: Path, root: Path, actor: str, actor_version: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    relative = path.relative_to(root).as_posix()
    started = utc_now()
    digest, size = sha256_file(path)
    stat = path.stat()
    guessed_mime, guessed_encoding = mimetypes.guess_type(path.name)
    metadata, diagnostics = extract_metadata(path)
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


def make_knowledge_records(assets: Iterable[dict[str, Any]], actor_version: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    previous_hash: str | None = None
    for asset in assets:
        body = {
            "schema": SCHEMA_VERSION,
            "knowledge_record_id": f"kr-{uuid.uuid4()}",
            "source_asset_id": asset["source_asset_id"],
            "source_asset_location": asset["source_asset_location"],
            "ingestion_timestamp": asset["ingestion_timestamp"],
            "ingestion_actor": asset["ingestion_actor"],
            "ingestion_actor_version": asset["ingestion_actor_version"],
            "extraction_method": "cookie-monster-alpha-metadata",
            "extraction_method_version": actor_version,
            "derivation_chain": [],
            "confidence": 1.0 if not asset["diagnostics"] else 0.7,
            "review_status": "pending_review" if asset["diagnostics"] else "draft",
            "supersedes": None,
            "superseded_by": None,
            "correction_reason": None,
            "previous_record_hash": previous_hash,
            "facts": {"filename": asset["filename"], "extension": asset["extension"], "size_bytes": asset["size_bytes"], "mime_type": asset["mime_type"]},
        }
        record_hash = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
        body["record_hash"] = f"sha256:{record_hash}"
        records.append(body)
        previous_hash = body["record_hash"]
    return records


def build_snapshot(source: Path, actor: str = DEFAULT_ACTOR, actor_version: str = "0.1.0-alpha", max_files: int | None = None) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for path in discover_files(source, max_files=max_files):
        asset, events = analyze_asset(path, source, actor, actor_version)
        assets.append(asset)
        audit.extend(events)
    duplicates = duplicate_groups(assets)
    records = make_knowledge_records(assets, actor_version)
    review_queue = [{"knowledge_record_id": record["knowledge_record_id"], "source_asset_id": record["source_asset_id"], "source_asset_location": record["source_asset_location"], "review_status": record["review_status"], "reason": "metadata_tool_diagnostic" if record["review_status"] == "pending_review" else "initial_alpha_record"} for record in records if record["review_status"] in {"draft", "pending_review"}]
    unique_assets = len({asset["source_asset_id"] for asset in assets})
    return {
        "schema": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "mode": "alpha-read-only",
        "source_kind": "staging",
        "pipeline_stages": list(PIPELINE_STAGES),
        "summary": {"files_discovered": len(assets), "unique_assets": unique_assets, "duplicate_groups": len(duplicates), "knowledge_records": len(records), "review_items": len(review_queue), "unauthorized_source_writes": 0},
        "tooling": tooling_status(),
        "fengus": {"connected": False, "mode": "not-connected-in-m0-m1", "jobs_active": 0, "jobs_completed": 0, "jobs_failed": 0},
        "assets": assets,
        "duplicates": duplicates,
        "knowledge_records": records,
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


def write_snapshot(snapshot: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    atomic_text(output / "status.json", json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    atomic_text(output / "knowledge-records.jsonl", "".join(canonical_json(row) + "\n" for row in snapshot["knowledge_records"]))
    atomic_text(output / "audit.jsonl", "".join(canonical_json(row) + "\n" for row in snapshot["audit"]))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cookie Monster Alpha read-only media ingestion")
    parser.add_argument("--source", required=True, type=Path, help="staging source directory (read only)")
    parser.add_argument("--output", required=True, type=Path, help="separate generated evidence/status directory")
    parser.add_argument("--actor", default=DEFAULT_ACTOR)
    parser.add_argument("--actor-version", default="0.1.0-alpha")
    parser.add_argument("--max-files", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        source, output = validate_paths(args.source, args.output)
        snapshot = build_snapshot(source, actor=args.actor, actor_version=args.actor_version, max_files=args.max_files)
        write_snapshot(snapshot, output)
    except AlphaBoundaryError as exc:
        print(f"cookie-monster-alpha: boundary error: {exc}", file=sys.stderr)
        return 2
    print(canonical_json({"status": "ok", "source": str(source), "output": str(output), "summary": snapshot["summary"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
