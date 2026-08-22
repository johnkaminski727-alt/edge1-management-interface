#!/usr/bin/env python3
"""Runtime wrapper for bounded Cookie Monster Alpha dataset execution.

Dataset names resolve through a repository-controlled registry. Callers never
supply an arbitrary source path. Disabled datasets fail closed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import cookie_monster_alpha as alpha
import cookie_monster_contract as contract

DEFAULT_REGISTRY = Path(__file__).parents[1] / "config" / "cookie_monster" / "datasets.json"


class RuntimeErrorBoundary(RuntimeError):
    pass


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeErrorBoundary(f"cannot load dataset registry: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != "wwcx.cookie-monster.datasets.v1":
        raise RuntimeErrorBoundary("unsupported dataset registry schema")
    datasets = value.get("datasets")
    if not isinstance(datasets, dict):
        raise RuntimeErrorBoundary("dataset registry is malformed")
    return value


def resolve_dataset(name: str, registry: dict[str, Any], require_enabled: bool = True) -> Path:
    datasets = registry.get("datasets", {})
    row = datasets.get(name)
    if not isinstance(row, dict):
        raise RuntimeErrorBoundary(f"dataset is not registered: {name}")
    if row.get("canonical_archive") is not False:
        raise RuntimeErrorBoundary("Alpha runtime refuses canonical archive datasets")
    if row.get("read_only_required") is not True:
        raise RuntimeErrorBoundary("dataset must require read-only source handling")
    if require_enabled and row.get("enabled") is not True:
        raise RuntimeErrorBoundary(f"dataset is disabled: {name}")
    source_root = row.get("source_root")
    if not isinstance(source_root, str) or not source_root.startswith("/srv/cookie-monster/staging/"):
        raise RuntimeErrorBoundary("dataset source root is outside the staging namespace")
    return Path(source_root)


def execute_job(request: dict[str, Any], output: Path, registry_path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    request = contract.validate(request)
    registry = load_registry(registry_path)
    source = resolve_dataset(request["dataset"], registry, require_enabled=True)
    source, output = alpha.validate_paths(source, output)
    existing = alpha.read_jsonl(output / "knowledge-records.jsonl")
    snapshot = alpha.build_snapshot(
        source,
        actor=request["requested_by"],
        actor_version="runtime-v1",
        max_files=request["max_files"],
        existing_records=existing,
        metadata_budget_seconds=float(request["metadata_budget_seconds"]),
        run_time_budget_seconds=float(request["run_budget_seconds"]),
    )
    snapshot["job"] = {
        "job_id": request["job_id"],
        "idempotency_key": request["idempotency_key"],
        "dataset": request["dataset"],
        "requested_by": request["requested_by"],
    }
    alpha.write_snapshot(snapshot, output)
    alpha.atomic_text(
        output / "job-status.json",
        json.dumps({
            "schema": "wwcx.cookie-monster.job-status.v1",
            "generated_at": alpha.utc_now(),
            "state": "completed",
            "job": request,
            "summary": snapshot["summary"],
        }, indent=2, sort_keys=True) + "\n",
    )
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one registered Cookie Monster Alpha job")
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args(argv)
    try:
        request = json.loads(args.job.read_text(encoding="utf-8"))
        snapshot = execute_job(request, args.output, registry_path=args.registry)
    except (OSError, json.JSONDecodeError, RuntimeErrorBoundary, contract.ContractError, alpha.AlphaBoundaryError) as exc:
        print(f"cookie-monster-runtime: {exc}", file=sys.stderr)
        return 2
    print(alpha.canonical_json({"status": "completed", "job": snapshot["job"], "summary": snapshot["summary"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
