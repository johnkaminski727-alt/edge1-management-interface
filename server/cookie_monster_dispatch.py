#!/usr/bin/env python3
"""Bounded Big Bird -> Cookie Monster Alpha dispatcher.

The Big Bird job envelope carries only a dataset slug. Runtime configuration
selects which non-production dataset slugs are enabled. The dispatcher never
accepts an archive path, output path, URL, command, or credential from the job.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
from typing import Any

import cookie_monster_alpha as alpha
import cookie_monster_contract as contract

REGISTRY_SCHEMA = "wwcx.cookie-monster.datasets.v1"
JOB_STATUS_SCHEMA = "wwcx.cookie-monster.job-status.v1"
DEFAULT_REGISTRY = Path("/etc/wwcx-cookie-monster/datasets.json")
DEFAULT_DATASET_ROOT = Path("/srv/cookie-monster/datasets")
DEFAULT_OUTPUT_ROOT = Path("/var/lib/cookie-monster-alpha/generated")
ALLOWED_DATASET_FIELDS = {"enabled", "non_production", "read_only", "description"}


class DispatchError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise DispatchError(f"symlink config/job file rejected: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DispatchError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DispatchError(f"JSON value must be an object: {path}")
    return value


def validate_registry(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) != {"schema", "datasets"}:
        raise DispatchError("dataset registry must contain exactly schema and datasets")
    if value.get("schema") != REGISTRY_SCHEMA:
        raise DispatchError("unsupported dataset registry schema")
    datasets = value.get("datasets")
    if not isinstance(datasets, dict):
        raise DispatchError("datasets must be an object")
    normalized: dict[str, Any] = {}
    for slug, entry in datasets.items():
        if not isinstance(slug, str) or not contract.DATASET_RE.fullmatch(slug):
            raise DispatchError(f"invalid dataset slug in registry: {slug!r}")
        if not isinstance(entry, dict):
            raise DispatchError(f"dataset entry must be an object: {slug}")
        extra = sorted(set(entry) - ALLOWED_DATASET_FIELDS)
        if extra:
            raise DispatchError(f"unexpected dataset fields for {slug}: {', '.join(extra)}")
        if type(entry.get("enabled")) is not bool:
            raise DispatchError(f"dataset enabled must be boolean: {slug}")
        if type(entry.get("non_production")) is not bool:
            raise DispatchError(f"dataset non_production must be boolean: {slug}")
        if type(entry.get("read_only")) is not bool:
            raise DispatchError(f"dataset read_only must be boolean: {slug}")
        description = entry.get("description", "")
        if not isinstance(description, str) or len(description) > 500:
            raise DispatchError(f"dataset description is invalid: {slug}")
        normalized[slug] = dict(entry)
    return {"schema": REGISTRY_SCHEMA, "datasets": normalized}


def _reject_symlink_components(root: Path, candidate: Path) -> None:
    root = root.resolve()
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise DispatchError("dataset path escapes approved dataset root") from exc
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise DispatchError(f"symlink component rejected in dataset path: {current}")


def resolve_dataset(registry: dict[str, Any], dataset_root: Path, slug: str) -> Path:
    registry = validate_registry(registry)
    entry = registry["datasets"].get(slug)
    if entry is None:
        raise DispatchError(f"dataset is not registered: {slug}")
    if entry["enabled"] is not True:
        raise DispatchError(f"dataset is disabled: {slug}")
    if entry["non_production"] is not True:
        raise DispatchError(f"dataset is not explicitly non-production: {slug}")
    if entry["read_only"] is not True:
        raise DispatchError(f"dataset is not explicitly read-only: {slug}")
    dataset_root = dataset_root.expanduser()
    if not dataset_root.is_absolute():
        raise DispatchError("dataset root must be absolute")
    if dataset_root.is_symlink():
        raise DispatchError("dataset root may not be a symlink")
    root = dataset_root.resolve()
    if not root.is_dir():
        raise DispatchError(f"dataset root does not exist: {root}")
    candidate = root / slug
    _reject_symlink_components(root, candidate)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise DispatchError("dataset resolves outside approved dataset root") from exc
    if not resolved.is_dir():
        raise DispatchError(f"dataset directory does not exist: {slug}")
    return resolved


def output_for(output_root: Path, dataset_root: Path, slug: str) -> Path:
    output_root = output_root.expanduser()
    if not output_root.is_absolute():
        raise DispatchError("output root must be absolute")
    resolved_output = output_root.resolve()
    resolved_dataset_root = dataset_root.expanduser().resolve()
    if resolved_output == resolved_dataset_root or alpha.is_within(resolved_output, resolved_dataset_root):
        raise DispatchError("generated output root may not be inside the staging dataset root")
    return resolved_output / slug


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def dispatch(job: dict[str, Any], registry: dict[str, Any], dataset_root: Path, output_root: Path) -> dict[str, Any]:
    job = contract.validate(job)
    if job["requested_stages"] != list(contract.PIPELINE_STAGES):
        raise DispatchError("Alpha dispatcher currently requires the complete ordered pipeline")
    source = resolve_dataset(registry, dataset_root, job["dataset"])
    output = output_for(output_root, dataset_root, job["dataset"])
    source, output = alpha.validate_paths(source, output)
    existing = alpha.read_jsonl(output / "knowledge-records.jsonl")
    started = utc_now()
    running = {
        "schema": JOB_STATUS_SCHEMA,
        "state": "running",
        "job": job,
        "dataset": job["dataset"],
        "source_kind": "non-production-staging",
        "started_at": started,
        "completed_at": None,
        "run_id": None,
        "summary": None,
    }
    atomic_json(output / "job-status.json", running)
    try:
        snapshot = alpha.build_snapshot(
            source,
            actor=f"bigbird:{job['requested_by']}",
            actor_version="cookie-monster-dispatch-v1",
            max_files=job["max_files"],
            existing_records=existing,
            metadata_budget_seconds=float(job["metadata_budget_seconds"]),
            run_time_budget_seconds=float(job["run_budget_seconds"]),
        )
        alpha.write_snapshot(snapshot, output)
    except Exception as exc:
        failed = dict(running)
        failed.update({"state": "failed", "completed_at": utc_now(), "error_type": type(exc).__name__})
        atomic_json(output / "job-status.json", failed)
        raise
    completed = dict(running)
    completed.update({
        "state": "completed",
        "completed_at": utc_now(),
        "run_id": snapshot.get("run_id"),
        "summary": snapshot.get("summary"),
    })
    atomic_json(output / "job-status.json", completed)
    return completed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dispatch a bounded Big Bird Cookie Monster job")
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args(argv)
    try:
        job = read_json(args.job)
        registry = validate_registry(read_json(args.registry))
        status = dispatch(job, registry, args.dataset_root, args.output_root)
    except (DispatchError, contract.ContractError, alpha.AlphaBoundaryError, OSError) as exc:
        print(f"cookie-monster-dispatch: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": status["state"], "job_id": status["job"]["job_id"], "dataset": status["dataset"], "run_id": status["run_id"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
