#!/usr/bin/env python3
"""Create bounded browser/operator JSON views from Cookie Monster evidence.

Raw append-only ledgers never enter the browser tree. Detail publication is
explicitly dataset-controlled and defaults to false for unknown/future data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import cookie_monster_alpha as alpha
import cookie_monster_runtime as runtime

VIEW_SCHEMA = "wwcx.cookie-monster.operator-view.v1"


class ViewError(RuntimeError):
    pass


def read_object(path: Path, required: bool = False) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise ViewError(f"required evidence is missing: {path.name}")
        return {}
    if path.is_symlink() or not path.is_file():
        raise ViewError(f"invalid evidence file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ViewError(f"invalid evidence JSON {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ViewError(f"evidence must be an object: {path.name}")
    return value


def dataset_policy(status: dict[str, Any], registry: dict[str, Any]) -> tuple[str | None, bool]:
    job = status.get("job") if isinstance(status.get("job"), dict) else {}
    dataset = job.get("dataset")
    if not isinstance(dataset, str):
        return None, False
    row = registry.get("datasets", {}).get(dataset)
    if not isinstance(row, dict):
        raise ViewError(f"runtime status references unregistered dataset: {dataset}")
    return dataset, row.get("operator_detail_publish") is True


def project_status(status: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    dataset, detail = dataset_policy(status, registry)
    tooling = status.get("tooling") if isinstance(status.get("tooling"), dict) else {}
    view: dict[str, Any] = {
        "schema": VIEW_SCHEMA,
        "generated_at": status.get("generated_at"),
        "run_id": status.get("run_id"),
        "mode": status.get("mode"),
        "source_kind": status.get("source_kind"),
        "dataset": dataset,
        "detail_published": detail,
        "summary": status.get("summary") if isinstance(status.get("summary"), dict) else {},
        "tooling": {name: {"available": bool(row.get("available"))} for name, row in tooling.items() if isinstance(row, dict)},
        "fengus": status.get("fengus") if isinstance(status.get("fengus"), dict) else {},
        "assets": [],
        "duplicates": [],
        "knowledge_records": [],
        "review_queue": [],
    }
    if detail:
        for row in status.get("assets", []):
            if not isinstance(row, dict):
                continue
            view["assets"].append({key: row.get(key) for key in ("source_asset_id", "source_asset_location", "filename", "extension", "size_bytes", "mime_type")})
        for row in status.get("duplicates", []):
            if isinstance(row, dict):
                view["duplicates"].append({key: row.get(key) for key in ("source_asset_id", "count", "locations")})
        for row in status.get("knowledge_records", []):
            if not isinstance(row, dict):
                continue
            view["knowledge_records"].append({key: row.get(key) for key in ("knowledge_record_id", "source_asset_id", "source_asset_location", "confidence", "review_status", "record_hash", "previous_record_hash", "extraction_method", "extraction_method_version", "facts")})
        for row in status.get("review_queue", []):
            if isinstance(row, dict):
                view["review_queue"].append({key: row.get(key) for key in ("knowledge_record_id", "source_asset_id", "source_asset_location", "review_status", "reason")})
    return view


def project_review(value: dict[str, Any], detail: bool) -> dict[str, Any]:
    rows = []
    for row in value.get("records", []):
        if not isinstance(row, dict):
            continue
        projected = {key: row.get(key) for key in ("knowledge_record_id", "source_asset_id", "review_status", "allowed_next")}
        if detail:
            projected["source_asset_location"] = row.get("source_asset_location")
        rows.append(projected)
    return {
        "schema": VIEW_SCHEMA,
        "generated_at": value.get("generated_at"),
        "summary": value.get("summary") if isinstance(value.get("summary"), dict) else {},
        "records": rows,
        "decision_events": value.get("decision_events", 0),
        "approval_owner": value.get("approval_owner"),
        "mutation_transport": value.get("mutation_transport"),
        "detail_published": detail,
    }


def project_job(value: dict[str, Any]) -> dict[str, Any]:
    job = value.get("job") if isinstance(value.get("job"), dict) else {}
    return {
        "schema": VIEW_SCHEMA,
        "generated_at": value.get("generated_at"),
        "state": value.get("state"),
        "job": {key: job.get(key) for key in ("schema", "mode", "job_id", "idempotency_key", "dataset", "requested_stages", "max_files", "metadata_budget_seconds", "run_budget_seconds")},
        "summary": value.get("summary") if isinstance(value.get("summary"), dict) else {},
    }


def project_acceptance(value: dict[str, Any]) -> dict[str, Any]:
    if not value:
        return {}
    return {
        "schema": VIEW_SCHEMA,
        "generated_at": value.get("generated_at"),
        "dataset": value.get("dataset"),
        "mode": value.get("mode"),
        "result": value.get("result"),
        "summary": value.get("summary") if isinstance(value.get("summary"), dict) else {},
        "criteria": value.get("criteria") if isinstance(value.get("criteria"), dict) else {},
    }


def build_views(generated: Path, registry_path: Path) -> dict[str, dict[str, Any]]:
    status = read_object(generated / "status.json", required=True)
    registry = runtime.load_registry(registry_path)
    status_view = project_status(status, registry)
    detail = bool(status_view["detail_published"])
    return {
        "status.json": status_view,
        "review-state.json": project_review(read_object(generated / "review-state.json"), detail),
        "job-status.json": project_job(read_object(generated / "job-status.json")),
        "acceptance.json": project_acceptance(read_object(generated / "acceptance.json")),
    }


def write_views(views: dict[str, dict[str, Any]], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, value in views.items():
        path = output / name
        if value:
            alpha.atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")
        elif path.exists():
            path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Cookie Monster bounded operator JSON views")
    parser.add_argument("--generated", type=Path, default=Path("/var/lib/cookie-monster-alpha/generated"))
    parser.add_argument("--output", type=Path, default=Path("/var/lib/cookie-monster-alpha/operator-view"))
    parser.add_argument("--registry", type=Path, default=runtime.DEFAULT_REGISTRY)
    args = parser.parse_args(argv)
    try:
        views = build_views(args.generated.resolve(), args.registry.resolve())
        write_views(views, args.output.resolve())
    except (OSError, ViewError, runtime.RuntimeErrorBoundary) as exc:
        print(f"cookie-monster-operator-view: {exc}", file=sys.stderr)
        return 2
    print(alpha.canonical_json({"status": "ok", "output": str(args.output), "files": sorted(name for name, value in views.items() if value)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
