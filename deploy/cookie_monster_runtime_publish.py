#!/usr/bin/env python3
"""Publish Cookie Monster runtime snapshots to the private Edge1 web root.

The publisher never writes into repository source or the generated evidence store.
It validates all runtime JSON before mutation, backs up every managed destination,
and emits a hash manifest. Rollback restores exactly the managed pre-change state.
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
STATIC_FILES = {
    "index.html": Path("src/web/cookie-monster/index.html"),
    "assets/mascot.webp": Path("src/web/cookie-monster/assets/mascot.webp"),
}
RUNTIME_FILES = ("status.json", "review-state.json", "job-status.json", "acceptance.json")
MANAGED_FILES = tuple(STATIC_FILES) + RUNTIME_FILES + ("runtime-manifest.json",)


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


def preflight(repo_root: Path, generated_root: Path, web_root: Path, backup_root: Path) -> dict[str, Any]:
    repo_root, generated_root, web_root, backup_root = validate_layout(repo_root, generated_root, web_root, backup_root)
    sources: dict[str, Path | None] = {}
    for dest_name, relative in STATIC_FILES.items():
        path = repo_root / relative
        if not path.is_file():
            raise PublishError(f"missing static source: {path}")
        sources[dest_name] = path
    status_path = generated_root / "status.json"
    if not status_path.is_file():
        raise PublishError(f"missing required runtime status: {status_path}")
    status = read_json(status_path)
    if status.get("schema") != STATUS_SCHEMA:
        raise PublishError(f"unexpected Cookie Monster status schema: {status.get('schema')!r}")
    sources["status.json"] = status_path
    runtime_presence: dict[str, bool] = {"status.json": True}
    for name in RUNTIME_FILES[1:]:
        path = generated_root / name
        if path.exists() and not path.is_file():
            raise PublishError(f"runtime snapshot is not a regular file: {path}")
        if path.is_file():
            read_json(path)
            sources[name] = path
            runtime_presence[name] = True
        else:
            sources[name] = None
            runtime_presence[name] = False
    return {
        "repo_root": repo_root,
        "generated_root": generated_root,
        "web_root": web_root,
        "backup_root": backup_root,
        "sources": sources,
        "runtime_presence": runtime_presence,
        "source_commit": source_commit(repo_root),
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


def build_manifest(plan: dict[str, Any]) -> dict[str, Any]:
    sources: dict[str, Path | None] = plan["sources"]
    files = {}
    for name, source in sources.items():
        if source is not None:
            files[name] = {"sha256": f"sha256:{sha256_file(source)}", "bytes": source.stat().st_size}
    return {
        "schema": MANIFEST_SCHEMA,
        "published_at": utc_now(),
        "source_commit": plan["source_commit"],
        "generated_root": str(plan["generated_root"]),
        "files": files,
    }


def apply(plan: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    web_root: Path = plan["web_root"]
    backup_root: Path = plan["backup_root"]
    sources: dict[str, Path | None] = plan["sources"]
    backup_dir = backup_destination(web_root, backup_root)
    web_root.mkdir(parents=True, exist_ok=True)
    os.chmod(web_root, 0o755)
    for name, source in sources.items():
        destination = web_root / name
        if source is None:
            if destination.is_file() or destination.is_symlink():
                destination.unlink()
            continue
        atomic_copy(source, destination)
    manifest = build_manifest(plan)
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
    p = argparse.ArgumentParser(description="Publish Cookie Monster runtime state to the private Edge1 web root")
    p.add_argument("--repo-root", type=Path, default=Path("/opt/edge1-management-interface"))
    p.add_argument("--generated-root", type=Path, default=Path("/var/lib/cookie-monster-alpha/generated"))
    p.add_argument("--web-root", type=Path, default=Path("/var/www/edge1-status/cookie-monster"))
    p.add_argument("--backup-root", type=Path, default=Path("/var/backups"))
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
        plan = preflight(args.repo_root, args.generated_root, args.web_root, args.backup_root)
        if not args.apply:
            print(json.dumps({
                "status": "preflight-ok",
                "source_commit": plan["source_commit"],
                "web_root": str(plan["web_root"]),
                "runtime_presence": plan["runtime_presence"],
            }, sort_keys=True))
            return 0
        backup_dir, manifest = apply(plan)
        print(json.dumps({
            "status": "published",
            "backup": str(backup_dir),
            "web_root": str(plan["web_root"]),
            "manifest_schema": manifest["schema"],
            "source_commit": manifest["source_commit"],
        }, sort_keys=True))
        return 0
    except PublishError as exc:
        print(f"cookie-monster-runtime-publish: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
