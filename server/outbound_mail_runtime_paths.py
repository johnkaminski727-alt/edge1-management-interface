#!/usr/bin/env python3
"""Strict runtime path boundary for the outbound-mail gateway.

Committed relative paths remain confined to the repository. Absolute runtime
configuration is allowed only under `/etc/wwcx`; mutable state is allowed only
under `/var/lib/wwcx-outbound-mail`. Symlinks, broad permissions, path escapes,
and misplaced config/state fail closed.
"""

from __future__ import annotations

import stat
from pathlib import Path
from typing import Iterable

import outbound_mail_gateway as gateway


DEFAULT_CONFIG_ROOT = Path("/etc/wwcx")
DEFAULT_STATE_ROOT = Path("/var/lib/wwcx-outbound-mail")


class RuntimePathError(gateway.ConfigurationError):
    """Raised when a runtime config or state path violates its boundary."""


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _reject_symlink_components(path: Path, stop: Path) -> None:
    current = path
    while _inside(current, stop):
        if current.exists() and current.is_symlink():
            raise RuntimePathError(f"runtime path contains a symlink: {current}")
        if current == stop:
            return
        current = current.parent
    raise RuntimePathError("runtime path escaped its approved root")


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _resolve_repository_path(repo: Path, value: Path, label: str) -> Path:
    try:
        return gateway.resolve_repo_path(repo, str(value))
    except gateway.ConfigurationError as exc:
        raise RuntimePathError(f"{label} escaped the repository root") from exc


def resolve_config_file(
    configured: str | Path,
    *,
    repo_root: str | Path,
    config_root: str | Path = DEFAULT_CONFIG_ROOT,
    require_root_owned: bool = True,
) -> Path:
    value = Path(configured)
    repo = Path(repo_root).resolve()
    if not value.is_absolute():
        candidate = _resolve_repository_path(repo, value, "repository configuration path")
        if not candidate.is_file() or candidate.is_symlink():
            raise RuntimePathError("repository configuration file is absent or unsafe")
        return candidate

    root_input = Path(config_root).absolute()
    root = root_input.resolve(strict=False)
    candidate_input = value.absolute()
    if candidate_input.exists() and candidate_input.is_symlink():
        raise RuntimePathError("runtime configuration file is a symlink")
    candidate = candidate_input.resolve(strict=False)
    if not _inside(candidate, root):
        raise RuntimePathError("absolute configuration path is outside /etc/wwcx")
    _reject_symlink_components(candidate_input.parent, root_input)
    _reject_symlink_components(root_input, root_input)
    if not candidate.is_file():
        raise RuntimePathError("runtime configuration file is absent or unsafe")
    mode = _mode(candidate)
    if mode & 0o022:
        raise RuntimePathError(
            f"runtime configuration file is group/world writable: {mode:04o}"
        )
    if require_root_owned and candidate.stat().st_uid != 0:
        raise RuntimePathError("runtime configuration file is not root-owned")
    return candidate


def resolve_state_path(
    configured: str | Path,
    *,
    repo_root: str | Path,
    state_root: str | Path = DEFAULT_STATE_ROOT,
) -> Path:
    value = Path(configured)
    repo = Path(repo_root).resolve()
    if not value.is_absolute():
        return _resolve_repository_path(repo, value, "repository mutable-state path")

    root_input = Path(state_root).absolute()
    root = root_input.resolve(strict=False)
    candidate_input = value.absolute()
    if candidate_input.exists() and candidate_input.is_symlink():
        raise RuntimePathError("mutable state file is a symlink")
    candidate = candidate_input.resolve(strict=False)
    if not _inside(candidate, root):
        raise RuntimePathError(
            "absolute mutable state path is outside /var/lib/wwcx-outbound-mail"
        )
    _reject_symlink_components(candidate_input.parent, root_input)
    _reject_symlink_components(root_input, root_input)
    if candidate.exists():
        if not candidate.is_file():
            raise RuntimePathError("existing mutable state path is not a regular file")
        mode = _mode(candidate)
        if mode & 0o077:
            raise RuntimePathError(
                f"existing mutable state file permissions are too broad: {mode:04o}"
            )
    return candidate


def validate_runtime_roots(
    config_root: str | Path = DEFAULT_CONFIG_ROOT,
    state_root: str | Path = DEFAULT_STATE_ROOT,
) -> tuple[Path, Path]:
    config = Path(config_root).resolve(strict=False)
    state = Path(state_root).resolve(strict=False)
    if config == state or _inside(config, state) or _inside(state, config):
        raise RuntimePathError("runtime configuration and mutable state roots overlap")
    return config, state


def summarize_paths(paths: Iterable[Path]) -> list[str]:
    return [str(item) for item in paths]
