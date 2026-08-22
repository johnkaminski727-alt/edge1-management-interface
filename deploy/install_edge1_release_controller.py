#!/usr/bin/env python3
"""Backup-first installer for the persistent Edge1 release controller.

Default execution is a read-only preflight. ``--apply`` installs only the
controller executable, its read-only status timer, and the release-manager
status page.  It also creates a dedicated mutable source checkout when one does
not already exist.  It does *not* switch the running control plane, install the
release-root service drop-ins, or promote a commit; those are separate explicit
release-controller actions.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
from typing import Any


EXPECTED_REPO = Path("/opt/edge1-management-interface")
LEGACY_ROOT = Path("/opt/edge1-management-interface")
SOURCE_ROOT = Path("/opt/edge1-management-source")
INSTALL_ROOT = Path("/usr/local/libexec")
CONTROLLER_DEST = INSTALL_ROOT / "edge1-release-controller"
SYSTEMD_ROOT = Path("/etc/systemd/system")
SERVICE_DEST = SYSTEMD_ROOT / "edge1-release-controller-status.service"
TIMER_DEST = SYSTEMD_ROOT / "edge1-release-controller-status.timer"
WEB_ROOT = Path("/var/www/edge1-status/release-manager")
WEB_DEST = WEB_ROOT / "index.html"
BACKUP_ROOT = Path("/var/backups")
SOURCE_USER = "wwadmin"
SCHEMA = "wwcx.edge1-release-controller-install.v1"


class InstallError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with temp.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temp, mode)
    os.replace(temp, path)


def run(argv: list[str], *, timeout: int = 180, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            argv,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
    except subprocess.TimeoutExpired as exc:
        raise InstallError(f"command timed out: {argv[0]}") from exc
    if check and result.returncode != 0:
        raise InstallError(f"command failed ({argv[0]} rc={result.returncode}): {(result.stderr or '').strip()[-2000:]}")
    return result


def repo_assets(repo: Path) -> dict[str, Path]:
    return {
        "controller": repo / "server/edge1_release_controller.py",
        "service": repo / "deploy/edge1-release-controller/edge1-release-controller-status.service",
        "timer": repo / "deploy/edge1-release-controller/edge1-release-controller-status.timer",
        "web": repo / "src/web/release-manager/index.html",
    }


def validate_repo(repo: Path) -> dict[str, Any]:
    repo = repo.expanduser().resolve()
    if not repo.is_dir():
        raise InstallError(f"repository missing: {repo}")
    assets = repo_assets(repo)
    missing = [str(path.relative_to(repo)) for path in assets.values() if path.is_symlink() or not path.is_file()]
    if missing:
        raise InstallError("installer source is missing or unsafe: " + ", ".join(missing))
    head = run(["git", "-c", f"safe.directory={repo}", "-C", str(repo), "rev-parse", "HEAD"], check=False)
    return {
        "repo": str(repo),
        "repo_head": (head.stdout or "").strip() if head.returncode == 0 else None,
        "assets": {name: {"sha256": sha256_file(path)} for name, path in assets.items()},
    }


def source_snapshot(source: Path = SOURCE_ROOT) -> dict[str, Any]:
    if source.is_symlink() or not source.is_dir():
        return {"present": False, "branch": None, "head": None, "dirty": None}
    prefix = ["git", "-c", f"safe.directory={source}", "-C", str(source)]
    head = run(prefix + ["rev-parse", "HEAD"], check=False)
    branch = run(prefix + ["symbolic-ref", "--short", "HEAD"], check=False)
    dirty = run(prefix + ["status", "--porcelain"], check=False)
    return {
        "present": head.returncode == 0,
        "branch": (branch.stdout or "").strip() or None,
        "head": (head.stdout or "").strip() or None,
        "dirty": bool((dirty.stdout or "").strip()) if dirty.returncode == 0 else None,
    }


def ensure_source_clone(legacy: Path = LEGACY_ROOT, source: Path = SOURCE_ROOT) -> dict[str, Any]:
    existing = source_snapshot(source)
    if existing["present"]:
        if existing["branch"] != "main":
            raise InstallError("existing dedicated source checkout is not on main")
        if existing["dirty"]:
            raise InstallError("existing dedicated source checkout is dirty")
        return {"created": False, **existing}
    if source.exists() or source.is_symlink():
        raise InstallError("dedicated source path exists but is not a usable Git checkout")
    if not legacy.exists():
        raise InstallError("legacy management repository is unavailable for local bootstrap clone")
    user = pwd.getpwnam(SOURCE_USER)
    source.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--no-hardlinks", str(legacy), str(source)], timeout=300)
    prefix = ["git", "-c", f"safe.directory={source}", "-C", str(source)]
    branch = run(prefix + ["symbolic-ref", "--short", "HEAD"], check=False)
    if (branch.stdout or "").strip() != "main":
        remote_main = run(prefix + ["show-ref", "--verify", "--quiet", "refs/remotes/origin/main"], check=False)
        local_main = run(prefix + ["show-ref", "--verify", "--quiet", "refs/heads/main"], check=False)
        if remote_main.returncode == 0:
            run(prefix + ["checkout", "-B", "main", "refs/remotes/origin/main"])
        elif local_main.returncode == 0:
            run(prefix + ["checkout", "main"])
        else:
            raise InstallError("bootstrap clone does not contain a main branch or origin/main ref")
    run(["chown", "-R", f"{user.pw_uid}:{user.pw_gid}", str(source)], timeout=300)
    snapshot = source_snapshot(source)
    if snapshot["branch"] != "main" or snapshot["dirty"]:
        raise InstallError("dedicated source checkout failed post-create validation")
    return {"created": True, **snapshot}


def backup_one(source: Path, backup: Path, name: str) -> dict[str, Any]:
    if source.is_symlink():
        raise InstallError(f"managed install destination may not be a symlink: {source}")
    entry: dict[str, Any] = {"path": str(source), "present": False, "sha256": None}
    if source.exists():
        if not source.is_file():
            raise InstallError(f"managed install destination is not a regular file: {source}")
        destination = backup / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        entry["present"] = True
        entry["sha256"] = sha256_file(destination)
    return entry


def restore_one(entry: dict[str, Any], backup: Path, name: str) -> None:
    destination = Path(entry["path"])
    if entry.get("present"):
        source = backup / name
        if sha256_file(source) != entry.get("sha256"):
            raise InstallError(f"backup hash mismatch: {name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_name(f".{destination.name}.restore-{os.getpid()}")
        shutil.copy2(source, temp)
        os.replace(temp, destination)
    elif destination.exists() or destination.is_symlink():
        destination.unlink()


def install_one(source: Path, destination: Path, mode: int) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    shutil.copy2(source, temp)
    os.chmod(temp, mode)
    os.replace(temp, destination)
    return sha256_file(destination)


def timer_enabled() -> bool:
    return run(["systemctl", "is-enabled", "--quiet", "edge1-release-controller-status.timer"], check=False).returncode == 0


def preflight(repo: Path) -> dict[str, Any]:
    validated = validate_repo(repo)
    source = source_snapshot()
    return {
        "schema": SCHEMA,
        "status": "preflight-ok",
        "repo": validated,
        "dedicated_source": source,
        "controller_installed": CONTROLLER_DEST.is_file() and not CONTROLLER_DEST.is_symlink(),
        "timer_installed": TIMER_DEST.is_file() and not TIMER_DEST.is_symlink(),
        "timer_enabled": timer_enabled(),
        "runtime_switch_performed": False,
        "managed_service_restart_performed": False,
    }


def apply(repo: Path) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise InstallError("--apply requires root")
    repo = repo.expanduser().resolve()
    validated = validate_repo(repo)
    assets = repo_assets(repo)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = BACKUP_ROOT / f"edge1-release-controller-install-{stamp}-{os.getpid()}"
    backup.mkdir(parents=True, exist_ok=False)
    os.chmod(backup, 0o700)
    was_enabled = timer_enabled()
    backups = {
        "controller": backup_one(CONTROLLER_DEST, backup, "edge1-release-controller"),
        "service": backup_one(SERVICE_DEST, backup, "edge1-release-controller-status.service"),
        "timer": backup_one(TIMER_DEST, backup, "edge1-release-controller-status.timer"),
        "web": backup_one(WEB_DEST, backup, "release-manager-index.html"),
    }
    manifest = {
        "schema": SCHEMA,
        "started_at": utc_now(),
        "repo_head": validated["repo_head"],
        "timer_was_enabled": was_enabled,
        "backups": backups,
        "source_root": str(SOURCE_ROOT),
        "source_created_is_preserved_on_rollback": True,
    }
    atomic_json(backup / "install.json", manifest)
    try:
        source = ensure_source_clone()
        hashes = {
            "controller": install_one(assets["controller"], CONTROLLER_DEST, 0o755),
            "service": install_one(assets["service"], SERVICE_DEST, 0o644),
            "timer": install_one(assets["timer"], TIMER_DEST, 0o644),
            "web": install_one(assets["web"], WEB_DEST, 0o644),
        }
        run(["systemctl", "daemon-reload"], timeout=60)
        run(["systemctl", "start", "edge1-release-controller-status.service"], timeout=60)
        run(["systemctl", "enable", "--now", "edge1-release-controller-status.timer"], timeout=60)
        result = {
            **manifest,
            "completed_at": utc_now(),
            "status": "installed",
            "source": source,
            "installed_hashes": hashes,
            "backup_dir": str(backup),
            "runtime_switch_performed": False,
            "managed_service_restart_performed": False,
        }
        atomic_json(backup / "result.json", result)
        return result
    except Exception as exc:
        rollback_error: str | None = None
        try:
            run(["systemctl", "disable", "--now", "edge1-release-controller-status.timer"], timeout=60, check=False)
            restore_one(backups["controller"], backup, "edge1-release-controller")
            restore_one(backups["service"], backup, "edge1-release-controller-status.service")
            restore_one(backups["timer"], backup, "edge1-release-controller-status.timer")
            restore_one(backups["web"], backup, "release-manager-index.html")
            run(["systemctl", "daemon-reload"], timeout=60)
            if was_enabled:
                run(["systemctl", "enable", "--now", "edge1-release-controller-status.timer"], timeout=60)
        except Exception as rollback_exc:  # pragma: no cover
            rollback_error = f"{type(rollback_exc).__name__}: {rollback_exc}"
        failed = {
            **manifest,
            "completed_at": utc_now(),
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "rollback_error": rollback_error,
            "backup_dir": str(backup),
        }
        atomic_json(backup / "result.json", failed)
        raise InstallError(f"install failed; rollback_error={rollback_error}: {exc}") from exc


def rollback(backup: Path) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise InstallError("--rollback requires root")
    backup = backup.expanduser().resolve()
    if BACKUP_ROOT.resolve() not in backup.parents or not backup.name.startswith("edge1-release-controller-install-"):
        raise InstallError("rollback path is outside the release-controller install backup namespace")
    manifest_path = backup / "install.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise InstallError("rollback manifest missing")
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise InstallError("rollback manifest schema mismatch")
    backups = value.get("backups")
    if not isinstance(backups, dict):
        raise InstallError("rollback manifest backups missing")
    run(["systemctl", "disable", "--now", "edge1-release-controller-status.timer"], timeout=60, check=False)
    restore_one(backups["controller"], backup, "edge1-release-controller")
    restore_one(backups["service"], backup, "edge1-release-controller-status.service")
    restore_one(backups["timer"], backup, "edge1-release-controller-status.timer")
    restore_one(backups["web"], backup, "release-manager-index.html")
    run(["systemctl", "daemon-reload"], timeout=60)
    if value.get("timer_was_enabled"):
        run(["systemctl", "enable", "--now", "edge1-release-controller-status.timer"], timeout=60)
    return {
        "schema": SCHEMA,
        "status": "rolled-back",
        "backup_dir": str(backup),
        "dedicated_source_preserved": True,
        "runtime_switch_performed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install the persistent Edge1 release controller")
    parser.add_argument("--repo", default=str(EXPECTED_REPO))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--rollback")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.rollback:
            value = rollback(Path(args.rollback))
        elif args.apply:
            value = apply(Path(args.repo))
        else:
            value = preflight(Path(args.repo))
    except (InstallError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": SCHEMA, "status": "error", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
