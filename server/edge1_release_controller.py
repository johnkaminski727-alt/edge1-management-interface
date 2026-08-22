#!/usr/bin/env python3
"""Durable release controller for the Edge1 management control plane.

The mutable source checkout and the running control-plane code are deliberately
separate.  Releases are exact commit-pinned local clones under a dedicated
runtime root.  Promotion atomically switches one ``current`` symlink, restarts
only a fixed service set, verifies health and repository-root stability, and
rolls back automatically on a failed postflight.

This controller never accepts an arbitrary command, path, service name, URL, or
branch.  It does not auto-deploy ``main``.  Every promotion is pinned to one
explicit 40-character commit SHA that must already be reachable from the local
``origin/main`` ref in the dedicated source checkout.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Callable
import urllib.error
import urllib.request


SCHEMA = "wwcx.edge1-release-controller.v1"
STATUS_SCHEMA = "wwcx.edge1-release-status.v1"
SOURCE_ROOT = Path("/opt/edge1-management-source")
RUNTIME_ROOT = Path("/opt/edge1-runtime")
RELEASES_ROOT = RUNTIME_ROOT / "releases"
CURRENT_LINK = RUNTIME_ROOT / "current"
PREVIOUS_LINK = RUNTIME_ROOT / "previous"
STATE_ROOT = Path("/var/lib/edge1-release-controller")
STATE_FILE = STATE_ROOT / "state.json"
STATUS_FILE = STATE_ROOT / "status.json"
BACKUP_ROOT = Path("/var/backups")
WEB_ROOT = Path("/var/www/edge1-status/release-manager")
WEB_STATUS = WEB_ROOT / "status.json"
INSTALL_ROOT = Path("/usr/local/libexec")
INSTALLED_CONTROLLER = INSTALL_ROOT / "edge1-release-controller"
OPERATIONS_DROPIN = Path("/etc/systemd/system/edge1-operations-api.service.d/20-edge1-release-root.conf")
OPERATOR_DROPIN = Path("/etc/systemd/system/edge1-operator-mcp.service.d/20-edge1-release-root.conf")
OPERATIONS_HEALTH_URL = "http://127.0.0.1:8097/healthz"
MANAGED_SERVICES = ("edge1-operations-api.service", "edge1-operator-mcp.service")
MANAGED_PORTS = (8097, 8102)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_OUTPUT = 16000


class ReleaseError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_bytes(path: Path, value: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temp.open("wb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temp, mode)
    os.replace(temp, path)


def atomic_json(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    atomic_bytes(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"), mode)


def load_json_object(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReleaseError(f"state file is missing or unsafe: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"invalid state JSON: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise ReleaseError("state JSON must be an object")
    return value


def run_command(
    argv: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    if not argv or not all(isinstance(item, str) and item for item in argv):
        raise ReleaseError("invalid command vector")
    try:
        result = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
    except subprocess.TimeoutExpired as exc:
        raise ReleaseError(f"command timed out: {argv[0]}") from exc
    if check and result.returncode != 0:
        stderr = (result.stderr or "").strip()[-2000:]
        raise ReleaseError(f"command failed ({argv[0]} rc={result.returncode}): {stderr}")
    return result


def http_json(url: str = OPERATIONS_HEALTH_URL, timeout: float = 3.0) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "WWCX-Edge1-Release-Controller/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read(65536)
    except (OSError, urllib.error.URLError) as exc:
        raise ReleaseError(f"operations health unavailable: {type(exc).__name__}") from exc
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError("operations health returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise ReleaseError("operations health must be a JSON object")
    return value


def valid_sha(value: str) -> str:
    normalized = value.strip().lower()
    if not SHA_RE.fullmatch(normalized):
        raise ReleaseError("target must be an exact 40-character lowercase hexadecimal commit SHA")
    return normalized


def _within(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents


class ReleaseController:
    def __init__(
        self,
        *,
        source_root: Path = SOURCE_ROOT,
        runtime_root: Path = RUNTIME_ROOT,
        state_root: Path = STATE_ROOT,
        backup_root: Path = BACKUP_ROOT,
        web_root: Path = WEB_ROOT,
        runner: Callable[..., subprocess.CompletedProcess[str]] = run_command,
        health_reader: Callable[..., dict[str, Any]] = http_json,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.source_root = source_root
        self.runtime_root = runtime_root
        self.releases_root = runtime_root / "releases"
        self.current_link = runtime_root / "current"
        self.previous_link = runtime_root / "previous"
        self.state_root = state_root
        self.state_file = state_root / "state.json"
        self.status_file = state_root / "status.json"
        self.backup_root = backup_root
        self.web_root = web_root
        self.web_status = web_root / "status.json"
        self.runner = runner
        self.health_reader = health_reader
        self.sleep = sleep

    def _run(self, argv: list[str], *, cwd: Path | None = None, timeout: int = 120, check: bool = True):
        return self.runner(argv, cwd=cwd, timeout=timeout, check=check)

    def _git(self, root: Path, *args: str, check: bool = True, timeout: int = 120):
        return self._run(
            ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
            timeout=timeout,
            check=check,
        )

    def _git_text(self, root: Path, *args: str, check: bool = True) -> str:
        return (self._git(root, *args, check=check).stdout or "").strip()

    def source_snapshot(self) -> dict[str, Any]:
        if self.source_root.is_symlink() or not self.source_root.is_dir():
            return {"available": False, "branch": None, "head": None, "dirty": None, "origin_main": None}
        try:
            head = self._git_text(self.source_root, "rev-parse", "HEAD")
            branch = self._git_text(self.source_root, "symbolic-ref", "--short", "HEAD", check=False) or None
            dirty = bool(self._git_text(self.source_root, "status", "--porcelain"))
            origin_main = self._git_text(self.source_root, "rev-parse", "refs/remotes/origin/main", check=False) or None
        except ReleaseError:
            return {"available": False, "branch": None, "head": None, "dirty": None, "origin_main": None}
        return {
            "available": bool(SHA_RE.fullmatch(head)),
            "branch": branch,
            "head": head if SHA_RE.fullmatch(head) else None,
            "dirty": dirty,
            "origin_main": origin_main if SHA_RE.fullmatch(origin_main or "") else None,
        }

    def require_source(self) -> dict[str, Any]:
        snapshot = self.source_snapshot()
        if not snapshot["available"]:
            raise ReleaseError("dedicated source checkout is unavailable; run the release-controller installer first")
        if snapshot["branch"] != "main":
            raise ReleaseError("dedicated source checkout must be on branch main")
        if snapshot["dirty"]:
            raise ReleaseError("dedicated source checkout must be clean")
        if not snapshot["origin_main"]:
            raise ReleaseError("dedicated source checkout is missing refs/remotes/origin/main")
        return snapshot

    def require_target(self, target: str) -> tuple[str, dict[str, Any]]:
        target = valid_sha(target)
        snapshot = self.require_source()
        exists = self._git(self.source_root, "cat-file", "-e", f"{target}^{{commit}}", check=False)
        if exists.returncode != 0:
            raise ReleaseError("target commit is not present in the dedicated source checkout")
        ancestor = self._git(
            self.source_root,
            "merge-base",
            "--is-ancestor",
            target,
            "refs/remotes/origin/main",
            check=False,
        )
        if ancestor.returncode != 0:
            raise ReleaseError("target commit is not reachable from the local origin/main ref")
        return target, snapshot

    def release_path(self, target: str) -> Path:
        target = valid_sha(target)
        return self.releases_root / target

    def release_head(self, release: Path) -> str:
        if release.is_symlink() or not release.is_dir():
            raise ReleaseError(f"release directory is missing or unsafe: {release}")
        resolved = release.resolve(strict=True)
        if not _within(resolved, self.releases_root.resolve(strict=True)):
            raise ReleaseError("release directory escapes the release root")
        head = self._git_text(release, "rev-parse", "HEAD")
        if not SHA_RE.fullmatch(head):
            raise ReleaseError("release HEAD is invalid")
        dirty = self._git_text(release, "status", "--porcelain")
        if dirty:
            raise ReleaseError("release worktree is dirty")
        return head

    def prepare(self, target: str) -> dict[str, Any]:
        if os.geteuid() != 0:
            raise ReleaseError("prepare requires root")
        target, source = self.require_target(target)
        self.releases_root.mkdir(parents=True, exist_ok=True)
        release = self.release_path(target)
        if release.exists() or release.is_symlink():
            if release.is_symlink() or not release.is_dir():
                raise ReleaseError("existing release path is unsafe")
            head = self.release_head(release)
            if head != target:
                raise ReleaseError("existing release path contains a different commit")
            return {"schema": SCHEMA, "status": "already-prepared", "target": target, "source_head": source["head"]}

        temp = self.releases_root / f".{target}.prepare-{os.getpid()}"
        if temp.exists() or temp.is_symlink():
            raise ReleaseError("temporary release path already exists")
        try:
            self._run(
                ["git", "clone", "--no-hardlinks", "--no-checkout", str(self.source_root), str(temp)],
                timeout=300,
            )
            self._git(temp, "checkout", "--detach", target, timeout=180)
            if self.release_head(temp) != target:
                raise ReleaseError("prepared release HEAD does not match target")
            required = (
                temp / "server/edge1_operations_api.py",
                temp / "server/edge1_operator_http.py",
                temp / "server/edge1_release_controller.py",
                temp / "deploy/edge1-release-controller/edge1-operations-api-release.conf",
                temp / "deploy/edge1-release-controller/edge1-operator-mcp-release.conf",
            )
            missing = [str(path.relative_to(temp)) for path in required if path.is_symlink() or not path.is_file()]
            if missing:
                raise ReleaseError("prepared release is missing required control-plane files: " + ", ".join(missing))
            os.replace(temp, release)
        except Exception:
            if temp.exists() and temp.is_dir() and not temp.is_symlink():
                shutil.rmtree(temp, ignore_errors=True)
            raise

        meta = {
            "schema": SCHEMA,
            "prepared_at": utc_now(),
            "target": target,
            "source_head": source["head"],
            "release_head": self.release_head(release),
        }
        atomic_json(self.state_root / "releases" / f"{target}.json", meta, 0o600)
        return {"schema": SCHEMA, "status": "prepared", "target": target, "source_head": source["head"]}

    def _link_sha(self, link: Path) -> str | None:
        if not link.exists() and not link.is_symlink():
            return None
        if not link.is_symlink():
            raise ReleaseError(f"runtime pointer is not a symlink: {link}")
        try:
            resolved = link.resolve(strict=True)
            releases_resolved = self.releases_root.resolve(strict=True)
        except OSError as exc:
            raise ReleaseError(f"runtime pointer is broken: {link}") from exc
        if not _within(resolved, releases_resolved):
            raise ReleaseError(f"runtime pointer escapes release root: {link}")
        sha = resolved.name
        if not SHA_RE.fullmatch(sha):
            raise ReleaseError(f"runtime pointer target is not a commit release: {link}")
        if self.release_head(resolved) != sha:
            raise ReleaseError(f"runtime pointer release HEAD mismatch: {link}")
        return sha

    def current_sha(self) -> str | None:
        return self._link_sha(self.current_link)

    def previous_sha(self) -> str | None:
        return self._link_sha(self.previous_link)

    def _replace_link(self, link: Path, target_release: Path | None) -> None:
        link.parent.mkdir(parents=True, exist_ok=True)
        temp = link.with_name(f".{link.name}.tmp-{os.getpid()}")
        if temp.exists() or temp.is_symlink():
            temp.unlink()
        if target_release is None:
            if link.exists() or link.is_symlink():
                link.unlink()
            return
        resolved_release = target_release.resolve(strict=True)
        releases_resolved = self.releases_root.resolve(strict=True)
        if not _within(resolved_release, releases_resolved):
            raise ReleaseError("refusing runtime pointer outside releases root")
        os.symlink(resolved_release, temp)
        os.replace(temp, link)

    def _backup_file(self, source: Path, backup_dir: Path, name: str) -> dict[str, Any]:
        entry: dict[str, Any] = {"path": str(source), "present": False, "sha256": None}
        if source.is_symlink():
            raise ReleaseError(f"managed systemd drop-in may not be a symlink: {source}")
        if source.exists():
            if not source.is_file():
                raise ReleaseError(f"managed systemd drop-in is not a regular file: {source}")
            destination = backup_dir / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            entry["present"] = True
            entry["sha256"] = sha256_file(destination)
        return entry

    def _restore_file(self, entry: dict[str, Any], backup_dir: Path, name: str) -> None:
        destination = Path(entry["path"])
        if entry.get("present"):
            source = backup_dir / name
            if sha256_file(source) != entry.get("sha256"):
                raise ReleaseError(f"backup hash mismatch for {name}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp = destination.with_name(f".{destination.name}.restore-{os.getpid()}")
            shutil.copy2(source, temp)
            os.replace(temp, destination)
        elif destination.exists() or destination.is_symlink():
            destination.unlink()

    def _install_dropin(self, source: Path, destination: Path) -> str:
        if source.is_symlink() or not source.is_file():
            raise ReleaseError(f"release drop-in is missing or unsafe: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
        shutil.copy2(source, temp)
        os.chmod(temp, 0o644)
        os.replace(temp, destination)
        return sha256_file(destination)

    def _restart_services(self) -> None:
        self._run(["systemctl", "daemon-reload"], timeout=60)
        for service in MANAGED_SERVICES:
            self._run(["systemctl", "restart", service], timeout=90)

    def _service_active(self, service: str) -> bool:
        return self._run(["systemctl", "is-active", "--quiet", service], timeout=30, check=False).returncode == 0

    def _listener_hosts(self, port: int) -> list[str]:
        result = self._run(["ss", "-H", "-ltn"], timeout=30, check=False)
        if result.returncode != 0:
            return []
        hosts: list[str] = []
        suffix = f":{port}"
        for raw in (result.stdout or "").splitlines():
            parts = raw.split()
            if len(parts) < 4:
                continue
            local = parts[3]
            if not local.endswith(suffix):
                continue
            host = local[: -len(suffix)]
            host = host.strip("[]")
            hosts.append(host)
        return hosts

    def _postflight_once(self, target: str) -> dict[str, Any]:
        target = valid_sha(target)
        current = self.current_sha()
        if current != target:
            raise ReleaseError(f"runtime current pointer mismatch: expected {target}, got {current}")
        services = {service: self._service_active(service) for service in MANAGED_SERVICES}
        if not all(services.values()):
            raise ReleaseError("one or more managed control-plane services are inactive")
        health = self.health_reader()
        if health.get("status") != "ok":
            raise ReleaseError("Operations API health is not ok")
        if health.get("repository_root_stable") is not True:
            raise ReleaseError("Operations API repository root is not stable")
        if health.get("mutations_enabled") is not False:
            raise ReleaseError("Operations API mutations are not disabled")
        listeners: dict[str, list[str]] = {}
        for port in MANAGED_PORTS:
            hosts = self._listener_hosts(port)
            listeners[str(port)] = hosts
            if not hosts:
                raise ReleaseError(f"expected loopback listener is absent on port {port}")
            if any(host not in {"127.0.0.1", "::1"} for host in hosts):
                raise ReleaseError(f"managed port {port} is exposed beyond loopback")
        return {
            "target": target,
            "services": services,
            "operations_health": health,
            "listeners": listeners,
        }

    def wait_postflight(self, target: str, attempts: int = 12, interval: float = 1.0) -> dict[str, Any]:
        last: Exception | None = None
        for _ in range(attempts):
            try:
                return self._postflight_once(target)
            except ReleaseError as exc:
                last = exc
                self.sleep(interval)
        raise ReleaseError(f"postflight did not converge: {last}")

    def _transaction_dir(self, target: str, reason: str) -> Path:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_reason = "rollback" if reason == "rollback" else "promote"
        path = self.backup_root / f"edge1-release-controller-{safe_reason}-{stamp}-{os.getpid()}-{target[:12]}"
        path.mkdir(parents=True, exist_ok=False)
        os.chmod(path, 0o700)
        return path

    def _write_state(self, payload: dict[str, Any]) -> None:
        payload = {"schema": SCHEMA, **payload}
        atomic_json(self.state_file, payload, 0o600)

    def _refresh_installed_controller(self, release: Path) -> dict[str, Any]:
        source = release / "server/edge1_release_controller.py"
        if source.is_symlink() or not source.is_file():
            raise ReleaseError("release controller source is unavailable in promoted release")
        INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
        temp = INSTALLED_CONTROLLER.with_name(f".{INSTALLED_CONTROLLER.name}.tmp-{os.getpid()}")
        shutil.copy2(source, temp)
        os.chmod(temp, 0o755)
        os.replace(temp, INSTALLED_CONTROLLER)
        return {"path": str(INSTALLED_CONTROLLER), "sha256": sha256_file(INSTALLED_CONTROLLER)}

    def promote(self, target: str, *, reason: str = "promote") -> dict[str, Any]:
        if os.geteuid() != 0:
            raise ReleaseError("promotion requires root")
        target, source = self.require_target(target)
        prepared = self.prepare(target)
        release = self.release_path(target)
        old_current = self.current_sha()
        old_previous = self.previous_sha()
        if old_current == target:
            postflight = self.wait_postflight(target)
            return {
                "schema": SCHEMA,
                "status": "already-current",
                "target": target,
                "source_head": source["head"],
                "postflight": postflight,
            }

        tx = self._transaction_dir(target, reason)
        backups = {
            "operations_dropin": self._backup_file(OPERATIONS_DROPIN, tx, "edge1-operations-api-release.conf"),
            "operator_dropin": self._backup_file(OPERATOR_DROPIN, tx, "edge1-operator-mcp-release.conf"),
        }
        manifest = {
            "schema": SCHEMA,
            "transaction": reason,
            "started_at": utc_now(),
            "target": target,
            "source_head": source["head"],
            "old_current": old_current,
            "old_previous": old_previous,
            "backups": backups,
        }
        atomic_json(tx / "transaction.json", manifest, 0o600)

        rollback_ok = False
        try:
            dropin_hashes = {
                "edge1-operations-api": self._install_dropin(
                    release / "deploy/edge1-release-controller/edge1-operations-api-release.conf",
                    OPERATIONS_DROPIN,
                ),
                "edge1-operator-mcp": self._install_dropin(
                    release / "deploy/edge1-release-controller/edge1-operator-mcp-release.conf",
                    OPERATOR_DROPIN,
                ),
            }
            if old_current:
                self._replace_link(self.previous_link, self.release_path(old_current))
            self._replace_link(self.current_link, release)
            self._restart_services()
            postflight = self.wait_postflight(target)
            controller_install = self._refresh_installed_controller(release)
            completed = {
                **manifest,
                "completed_at": utc_now(),
                "status": "succeeded",
                "current": target,
                "previous": old_current,
                "dropin_hashes": dropin_hashes,
                "controller_install": controller_install,
                "postflight": postflight,
                "backup_dir": str(tx),
            }
            atomic_json(tx / "result.json", completed, 0o600)
            self._write_state(completed)
            return completed
        except Exception as exc:
            rollback_error: str | None = None
            try:
                self._replace_link(self.current_link, self.release_path(old_current) if old_current else None)
                self._replace_link(self.previous_link, self.release_path(old_previous) if old_previous else None)
                self._restore_file(backups["operations_dropin"], tx, "edge1-operations-api-release.conf")
                self._restore_file(backups["operator_dropin"], tx, "edge1-operator-mcp-release.conf")
                self._restart_services()
                if old_current:
                    self.wait_postflight(old_current)
                rollback_ok = True
            except Exception as rollback_exc:  # pragma: no cover - defensive emergency path
                rollback_error = f"{type(rollback_exc).__name__}: {rollback_exc}"
            failed = {
                **manifest,
                "completed_at": utc_now(),
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "automatic_rollback_succeeded": rollback_ok,
                "automatic_rollback_error": rollback_error,
                "backup_dir": str(tx),
            }
            atomic_json(tx / "result.json", failed, 0o600)
            self._write_state(failed)
            suffix = "automatic rollback succeeded" if rollback_ok else f"automatic rollback FAILED: {rollback_error}"
            raise ReleaseError(f"promotion failed; {suffix}: {exc}") from exc

    def rollback_last(self) -> dict[str, Any]:
        if os.geteuid() != 0:
            raise ReleaseError("rollback requires root")
        if not self.state_file.is_file() or self.state_file.is_symlink():
            raise ReleaseError("no durable release state is available for rollback")
        state = load_json_object(self.state_file)
        current = self.current_sha()
        previous = state.get("previous") or self.previous_sha()
        if not isinstance(previous, str) or not SHA_RE.fullmatch(previous):
            raise ReleaseError("no exact previous release is recorded")
        if current == previous:
            raise ReleaseError("previous release is already current")
        return self.promote(previous, reason="rollback")

    def status(self) -> dict[str, Any]:
        source = self.source_snapshot()
        errors: list[str] = []
        try:
            current = self.current_sha()
        except ReleaseError as exc:
            current = None
            errors.append(str(exc))
        try:
            previous = self.previous_sha()
        except ReleaseError as exc:
            previous = None
            errors.append(str(exc))
        services = {service: self._service_active(service) for service in MANAGED_SERVICES}
        try:
            health = self.health_reader()
        except ReleaseError as exc:
            health = {"status": "unavailable", "detail": str(exc)}
        listeners: dict[str, list[str]] = {str(port): self._listener_hosts(port) for port in MANAGED_PORTS}
        loopback_only = all(
            hosts and all(host in {"127.0.0.1", "::1"} for host in hosts)
            for hosts in listeners.values()
        )
        health_ok = (
            health.get("status") == "ok"
            and health.get("repository_root_stable") is True
            and health.get("mutations_enabled") is False
        )
        healthy = bool(current and all(services.values()) and health_ok and loopback_only and not errors)
        last: dict[str, Any] | None = None
        if self.state_file.is_file() and not self.state_file.is_symlink():
            try:
                raw = load_json_object(self.state_file)
                last = {
                    "status": raw.get("status"),
                    "transaction": raw.get("transaction"),
                    "target": raw.get("target"),
                    "completed_at": raw.get("completed_at"),
                    "automatic_rollback_succeeded": raw.get("automatic_rollback_succeeded"),
                }
            except ReleaseError as exc:
                errors.append(str(exc))
        return {
            "schema": STATUS_SCHEMA,
            "generated_at": utc_now(),
            "healthy": healthy,
            "action_required": not healthy,
            "source": source,
            "runtime": {
                "current": current,
                "previous": previous,
                "source_differs_from_runtime": bool(source.get("head") and current and source["head"] != current),
            },
            "services": services,
            "operations_api": {
                "status": health.get("status"),
                "repository_root_stable": health.get("repository_root_stable"),
                "mutations_enabled": health.get("mutations_enabled"),
            },
            "listeners": listeners,
            "loopback_only": loopback_only,
            "last_transaction": last,
            "errors": errors,
            "automatic_promotion": False,
        }

    def write_status(self, *, publish: bool = False) -> dict[str, Any]:
        value = self.status()
        atomic_json(self.status_file, value, 0o644)
        if publish:
            self.web_root.mkdir(parents=True, exist_ok=True)
            atomic_json(self.web_status, value, 0o644)
        return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Durable Edge1 runtime release controller")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="read current source/runtime/control-plane state")
    status.add_argument("--write-status", action="store_true")
    status.add_argument("--publish-status", action="store_true")

    prepare = sub.add_parser("prepare", help="prepare one exact commit as an immutable runtime release")
    prepare.add_argument("target")

    promote = sub.add_parser("promote", help="atomically promote one exact prepared commit")
    promote.add_argument("target")

    sub.add_parser("rollback-last", help="return to the exact recorded previous runtime release")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    controller = ReleaseController()
    try:
        if args.command == "status":
            value = controller.write_status(publish=args.publish_status) if args.write_status or args.publish_status else controller.status()
        elif args.command == "prepare":
            value = controller.prepare(args.target)
        elif args.command == "promote":
            value = controller.promote(args.target)
        elif args.command == "rollback-last":
            value = controller.rollback_last()
        else:  # pragma: no cover
            raise ReleaseError("unsupported command")
    except ReleaseError as exc:
        print(json.dumps({"schema": SCHEMA, "status": "error", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
