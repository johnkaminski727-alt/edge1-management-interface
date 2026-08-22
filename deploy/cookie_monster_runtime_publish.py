#!/usr/bin/env python3
"""Publish minimized Cookie Monster runtime snapshots to the Edge1 web root.

The publisher never writes into repository source or the generated evidence store.
It validates raw runtime JSON, projects a bounded browser/operator view, backs up
every managed destination, and emits a hash manifest. Rollback restores exactly
the managed pre-change state.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

MANIFEST_SCHEMA = "wwcx.cookie-monster.runtime-publication.v1"
STATUS_SCHEMA = "wwcx.cookie-monster.alpha.v1"
OPERATOR_VIEW_SCHEMA = "wwcx.cookie-monster.operator-view.v1"
STATIC_FILES = {
    "index.html": Path("src/web/cookie-monster/index.html"),
    "assets/mascot.webp": Path("src/web/cookie-monster/assets/mascot.webp"),
}
RUNTIME_FILES = ("status.json", "review-state.json", "job-status.json", "acceptance.json")
MANAGED_FILES = tuple(STATIC_FILES) + RUNTIME_FILES + ("runtime-manifest.json",)
SUMMARY_FIELDS = (
    "files_discovered",
    "unique_assets",
    "duplicate_groups",
    "knowledge_records",
    "new_knowledge_records",
    "reused_knowledge_records",
    "review_items",
    "unauthorized_source_writes",
)
JOB_FIELDS = (
    "schema",
    "mode",
    "job_id",
    "idempotency_key",
    "dataset",
    "requested_stages",
    "max_files",
    "metadata_budget_seconds",
    "run_budget_seconds",
)


class PublishError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def validate_layout(repo_root: Path, generated_root: Path, web_root: Path, backup_root: Path) -> tuple[Path, Path, Path, Path]:
    repo_root = repo_root.expanduser().resolve()
    generated_root = generated_root.expanduser().resolve()
    web_root = web_root.expanduser().resolve()
    backup_root = backup_root.expanduser().resolve()
    if not repo_root.is_dir():
        raise PublishError(f"repository root does not exist: {repo_root}")
    if not generated_root.is_dir():
        raise PublishError(f"generated root does not exist: {generated_root}")
    if generated_root == repo_root or is_within(generated_root, repo_root):
        raise PublishError("generated runtime evidence must remain outside repository source")
    if web_root == repo_root or is_within(web_root, repo_root):
        raise PublishError("runtime web root must remain outside repository source")
    if web_root == generated_root or is_within(web_root, generated_root):
        raise PublishError("runtime web root must not be inside the generated evidence store")
    if backup_root == repo_root or is_within(backup_root, repo_root):
        raise PublishError("backup root must remain outside repository source")
    return repo_root, generated_root, web_root, backup_root


def read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise PublishError(f"runtime snapshot may not be a symlink: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublishError(f"invalid JSON snapshot {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PublishError(f"snapshot must contain a JSON object: {path}")
    return value


def source_commit(repo_root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and len(value) == 40 else None


def _bounded_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {key: value.get(key) for key in SUMMARY_FIELDS if key in value and isinstance(value.get(key), (int, float, bool))}


def _safe_criterion_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str) and len(value) <= 160 and "/" not in value and "\\" not in value:
        return value
    return None


def project_status(status: dict[str, Any], publish_detail: bool = False) -> dict[str, Any]:
    if status.get("schema") != STATUS_SCHEMA:
        raise PublishError(f"unexpected Cookie Monster status schema: {status.get('schema')!r}")
    summary = _bounded_summary(status.get("summary"))
    if publish_detail:
        if status.get("mode") != "alpha-read-only":
            raise PublishError("detail publication requires alpha-read-only status")
        if status.get("source_kind") not in {"staging", "non-production-staging"}:
            raise PublishError("detail publication requires an explicitly non-production staging source")
        if summary.get("unauthorized_source_writes") != 0:
            raise PublishError("detail publication requires zero unauthorized source writes")
    tooling = status.get("tooling") if isinstance(status.get("tooling"), dict) else {}
    fengus = status.get("fengus") if isinstance(status.get("fengus"), dict) else {}
    view: dict[str, Any] = {
        "schema": OPERATOR_VIEW_SCHEMA,
        "source_schema": STATUS_SCHEMA,
        "generated_at": status.get("generated_at"),
        "run_id": status.get("run_id"),
        "mode": status.get("mode"),
        "source_kind": status.get("source_kind"),
        "detail_published": publish_detail,
        "summary": summary,
        "tooling": {
            name: {"available": bool(row.get("available"))}
            for name, row in tooling.items()
            if isinstance(name, str) and isinstance(row, dict)
        },
        "fengus": {
            key: fengus.get(key)
            for key in ("connected", "mode", "jobs_active", "jobs_completed", "jobs_failed")
            if key in fengus
        },
        "assets": [],
        "duplicates": [],
        "knowledge_records": [],
        "review_queue": [],
    }
    if not publish_detail:
        return view
    for row in status.get("assets", []):
        if not isinstance(row, dict):
            continue
        view["assets"].append({
            key: row.get(key)
            for key in ("source_asset_id", "source_asset_location", "filename", "extension", "size_bytes", "mime_type")
        })
    for row in status.get("duplicates", []):
        if isinstance(row, dict):
            view["duplicates"].append({key: row.get(key) for key in ("source_asset_id", "count", "locations")})
    for row in status.get("knowledge_records", []):
        if not isinstance(row, dict):
            continue
        facts = row.get("facts") if isinstance(row.get("facts"), dict) else {}
        view["knowledge_records"].append({
            "knowledge_record_id": row.get("knowledge_record_id"),
            "source_asset_id": row.get("source_asset_id"),
            "source_asset_location": row.get("source_asset_location"),
            "confidence": row.get("confidence"),
            "review_status": row.get("review_status"),
            "record_hash": row.get("record_hash"),
            "previous_record_hash": row.get("previous_record_hash"),
            "extraction_method": row.get("extraction_method"),
            "extraction_method_version": row.get("extraction_method_version"),
            "facts": {
                key: facts.get(key)
                for key in ("filename", "extension", "size_bytes", "mime_type")
                if key in facts
            },
        })
    for row in status.get("review_queue", []):
        if isinstance(row, dict):
            view["review_queue"].append({
                key: row.get(key)
                for key in ("knowledge_record_id", "source_asset_id", "source_asset_location", "review_status", "reason")
            })
    return view


def project_review(value: dict[str, Any] | None, publish_detail: bool = False) -> dict[str, Any] | None:
    if value is None:
        return None
    rows = []
    for row in value.get("records", []):
        if not isinstance(row, dict):
            continue
        projected = {
            key: row.get(key)
            for key in ("knowledge_record_id", "source_asset_id", "review_status", "allowed_next")
        }
        if publish_detail:
            projected["source_asset_location"] = row.get("source_asset_location")
        rows.append(projected)
    summary = value.get("summary") if isinstance(value.get("summary"), dict) else {}
    bounded_counts = {
        key: summary.get(key)
        for key in ("draft", "pending_review", "approved", "rejected")
        if isinstance(summary.get(key), int)
    }
    return {
        "schema": OPERATOR_VIEW_SCHEMA,
        "generated_at": value.get("generated_at"),
        "summary": bounded_counts,
        "records": rows,
        "decision_events": value.get("decision_events") if isinstance(value.get("decision_events"), int) else 0,
        "approval_owner": value.get("approval_owner") if isinstance(value.get("approval_owner"), str) else None,
        "mutation_transport": value.get("mutation_transport") if isinstance(value.get("mutation_transport"), str) else None,
        "detail_published": publish_detail,
    }


def project_job(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    job = value.get("job") if isinstance(value.get("job"), dict) else {}
    summary = value.get("summary") if isinstance(value.get("summary"), dict) else {}
    safe_summary = {
        key: item
        for key, item in summary.items()
        if isinstance(key, str) and isinstance(item, (bool, int, float))
    }
    return {
        "schema": OPERATOR_VIEW_SCHEMA,
        "generated_at": value.get("generated_at"),
        "state": value.get("state"),
        "job": {key: job.get(key) for key in JOB_FIELDS if key in job},
        "summary": safe_summary,
        "run_id": value.get("run_id"),
    }


def project_acceptance(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    criteria_out: dict[str, Any] = {}
    criteria = value.get("criteria") if isinstance(value.get("criteria"), dict) else {}
    for name, row in criteria.items():
        if not isinstance(name, str) or not isinstance(row, dict):
            continue
        criteria_out[name] = {
            "pass": row.get("pass") is True,
            "value": _safe_criterion_value(row.get("value")),
            "detail": "",
        }
    summary = value.get("summary") if isinstance(value.get("summary"), dict) else {}
    safe_summary = {
        key: item
        for key, item in summary.items()
        if isinstance(key, str) and isinstance(item, (bool, int, float))
    }
    return {
        "schema": OPERATOR_VIEW_SCHEMA,
        "generated_at": value.get("generated_at"),
        "dataset": value.get("dataset") if isinstance(value.get("dataset"), str) else None,
        "mode": value.get("mode") if isinstance(value.get("mode"), str) else None,
        "result": value.get("result") if isinstance(value.get("result"), str) else None,
        "summary": safe_summary,
        "criteria": criteria_out,
    }


def project_runtime(values: dict[str, dict[str, Any] | None], publish_detail: bool = False) -> dict[str, dict[str, Any] | None]:
    status = values.get("status.json")
    if status is None:
        raise PublishError("missing required runtime status")
    return {
        "status.json": project_status(status, publish_detail=publish_detail),
        "review-state.json": project_review(values.get("review-state.json"), publish_detail=publish_detail),
        "job-status.json": project_job(values.get("job-status.json")),
        "acceptance.json": project_acceptance(values.get("acceptance.json")),
    }


def preflight(
    repo_root: Path,
    generated_root: Path,
    web_root: Path,
    backup_root: Path,
    publish_detail: bool = False,
) -> dict[str, Any]:
    repo_root, generated_root, web_root, backup_root = validate_layout(repo_root, generated_root, web_root, backup_root)
    static_sources: dict[str, Path] = {}
    for dest_name, relative in STATIC_FILES.items():
        path = repo_root / relative
        if path.is_symlink() or not path.is_file():
            raise PublishError(f"missing or symlinked static source: {path}")
        static_sources[dest_name] = path
    status_path = generated_root / "status.json"
    if status_path.is_symlink() or not status_path.is_file():
        raise PublishError(f"missing required runtime status: {status_path}")
    runtime_values: dict[str, dict[str, Any] | None] = {"status.json": read_json(status_path)}
    runtime_presence: dict[str, bool] = {"status.json": True}
    for name in RUNTIME_FILES[1:]:
        path = generated_root / name
        if path.is_symlink():
            raise PublishError(f"runtime snapshot may not be a symlink: {path}")
        if path.exists() and not path.is_file():
            raise PublishError(f"runtime snapshot is not a regular file: {path}")
        if path.is_file():
            runtime_values[name] = read_json(path)
            runtime_presence[name] = True
        else:
            runtime_values[name] = None
            runtime_presence[name] = False
    runtime_views = project_runtime(runtime_values, publish_detail=publish_detail)
    return {
        "repo_root": repo_root,
        "generated_root": generated_root,
        "web_root": web_root,
        "backup_root": backup_root,
        "static_sources": static_sources,
        "runtime_views": runtime_views,
        "runtime_presence": runtime_presence,
        "source_commit": source_commit(repo_root),
        "detail_published": publish_detail,
    }


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    shutil.copyfile(source, tmp)
    os.chmod(tmp, 0o644)
    os.replace(tmp, destination)


def atomic_json(value: dict[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o644)
    os.replace(tmp, destination)


def backup_destination(web_root: Path, backup_root: Path) -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = backup_root / f"wwcx-cookie-monster-runtime-{stamp}-{os.getpid()}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    index: dict[str, Any] = {"schema": "wwcx.cookie-monster.runtime-backup.v1", "created_at": utc_now(), "files": {}}
    for name in MANAGED_FILES:
        current = web_root / name
        exists = current.is_file()
        index["files"][name] = {"present": exists}
        if exists:
            saved = backup_dir / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(current, saved)
            index["files"][name]["sha256"] = sha256_file(saved)
    atomic_json(index, backup_dir / "backup-index.json")
    return backup_dir


def build_manifest(web_root: Path, source_commit_value: str | None, detail_published: bool) -> dict[str, Any]:
    files: dict[str, Any] = {}
    for name in tuple(STATIC_FILES) + RUNTIME_FILES:
        path = web_root / name
        if path.is_file():
            files[name] = {"sha256": f"sha256:{sha256_file(path)}", "bytes": path.stat().st_size}
    return {
        "schema": MANIFEST_SCHEMA,
        "published_at": utc_now(),
        "source_commit": source_commit_value,
        "runtime_evidence_origin": "cookie-monster-generated",
        "detail_published": detail_published,
        "files": files,
    }


def apply(plan: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    web_root: Path = plan["web_root"]
    backup_root: Path = plan["backup_root"]
    static_sources: dict[str, Path] = plan["static_sources"]
    runtime_views: dict[str, dict[str, Any] | None] = plan["runtime_views"]
    backup_dir = backup_destination(web_root, backup_root)
    web_root.mkdir(parents=True, exist_ok=True)
    os.chmod(web_root, 0o755)
    for name, source in static_sources.items():
        atomic_copy(source, web_root / name)
    for name, value in runtime_views.items():
        destination = web_root / name
        if value is None:
            if destination.is_file() or destination.is_symlink():
                destination.unlink()
            continue
        atomic_json(value, destination)
    manifest = build_manifest(web_root, plan["source_commit"], bool(plan["detail_published"]))
    atomic_json(manifest, web_root / "runtime-manifest.json")
    return backup_dir, manifest


def rollback(backup_dir: Path, web_root: Path) -> None:
    backup_dir = backup_dir.expanduser().resolve()
    web_root = web_root.expanduser().resolve()
    index_path = backup_dir / "backup-index.json"
    index = read_json(index_path)
    if index.get("schema") != "wwcx.cookie-monster.runtime-backup.v1":
        raise PublishError("unsupported runtime backup schema")
    files = index.get("files")
    if not isinstance(files, dict) or set(files) != set(MANAGED_FILES):
        raise PublishError("runtime backup index does not exactly match the managed file set")
    for name in MANAGED_FILES:
        state = files[name]
        destination = web_root / name
        if state.get("present") is True:
            source = backup_dir / name
            if not source.is_file():
                raise PublishError(f"backup payload missing: {source}")
            expected = state.get("sha256")
            if expected and sha256_file(source) != expected:
                raise PublishError(f"backup hash mismatch: {source}")
            atomic_copy(source, destination)
        else:
            if destination.is_file() or destination.is_symlink():
                destination.unlink()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Publish minimized Cookie Monster runtime state to the Edge1 operator web root")
    p.add_argument("--repo-root", type=Path, default=Path("/opt/edge1-management-interface"))
    p.add_argument("--generated-root", type=Path, default=Path("/var/lib/cookie-monster-alpha/generated"))
    p.add_argument("--web-root", type=Path, default=Path("/var/www/edge1-status/cookie-monster"))
    p.add_argument("--backup-root", type=Path, default=Path("/var/backups"))
    p.add_argument(
        "--publish-detail",
        action="store_true",
        help="publish bounded filenames/relative locations only for verified alpha read-only non-production staging evidence",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--rollback", type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.rollback is not None:
            rollback(args.rollback, args.web_root)
            print(json.dumps({"status": "rolled-back", "backup": str(args.rollback), "web_root": str(args.web_root)}, sort_keys=True))
            return 0
        plan = preflight(
            args.repo_root,
            args.generated_root,
            args.web_root,
            args.backup_root,
            publish_detail=args.publish_detail,
        )
        if not args.apply:
            print(json.dumps({
                "status": "preflight-ok",
                "source_commit": plan["source_commit"],
                "web_root": str(plan["web_root"]),
                "runtime_presence": plan["runtime_presence"],
                "detail_published": plan["detail_published"],
            }, sort_keys=True))
            return 0
        backup_dir, manifest = apply(plan)
        print(json.dumps({
            "status": "published",
            "backup": str(backup_dir),
            "web_root": str(plan["web_root"]),
            "manifest_schema": manifest["schema"],
            "source_commit": manifest["source_commit"],
            "detail_published": manifest["detail_published"],
        }, sort_keys=True))
        return 0
    except PublishError as exc:
        print(f"cookie-monster-runtime-publish: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
