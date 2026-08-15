"""Candidate/running configuration workflow with atomic backup and rollback."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any

from .config import config_from_dict


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_valid(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("configuration must be a JSON object")
    config_from_dict(payload)
    return payload


def _canonical(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes, mode: int = 0o600, uid: int | None = None, gid: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, mode)
        if uid is not None or gid is not None:
            os.chown(temp_name, -1 if uid is None else uid, -1 if gid is None else gid)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _target_metadata(path: Path, *, default_mode: int = 0o600) -> tuple[int, int | None, int | None]:
    if not path.exists():
        return default_mode, None, None
    current = path.stat()
    return stat.S_IMODE(current.st_mode), current.st_uid, current.st_gid


def stage_config(source: str | Path, state_dir: str | Path) -> dict[str, Any]:
    source_path = Path(source)
    state = Path(state_dir)
    payload = _read_valid(source_path)
    data = _canonical(payload)
    candidate = state / "candidate.json"
    _atomic_write(candidate, data)
    metadata = {
        "staged_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": str(source_path),
        "candidate": str(candidate),
        "sha256": _sha256(data),
    }
    _atomic_write(state / "candidate-metadata.json", _canonical(metadata))
    return metadata


def apply_candidate(state_dir: str | Path, target: str | Path) -> dict[str, Any]:
    state = Path(state_dir)
    target_path = Path(target)
    candidate = state / "candidate.json"
    payload = _read_valid(candidate)
    data = _canonical(payload)
    backups = state / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None
    mode, uid, gid = _target_metadata(target_path)
    if target_path.exists():
        existing_payload = _read_valid(target_path)
        backup_path = backups / f"comms-relay.{utc_stamp()}.json"
        _atomic_write(backup_path, _canonical(existing_payload))
    _atomic_write(target_path, data, mode=mode, uid=uid, gid=gid)
    record = {
        "applied_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "target": str(target_path),
        "sha256": _sha256(data),
        "backup": str(backup_path) if backup_path else None,
        "restart_required": True,
        "preserved_mode": oct(mode),
        "preserved_uid": uid,
        "preserved_gid": gid,
    }
    _atomic_write(state / "last-applied.json", _canonical(record))
    return record


def rollback_last(state_dir: str | Path, target: str | Path) -> dict[str, Any]:
    state = Path(state_dir)
    target_path = Path(target)
    record_path = state / "last-applied.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if str(record.get("target")) != str(target_path):
        raise ValueError("last-applied target does not match requested rollback target")
    backup_value = record.get("backup")
    if not backup_value:
        raise ValueError("no prior running configuration backup is available")
    backup = Path(str(backup_value))
    payload = _read_valid(backup)
    current_backup = state / "backups" / f"pre-rollback.{utc_stamp()}.json"
    mode, uid, gid = _target_metadata(target_path)
    if target_path.exists():
        shutil.copy2(target_path, current_backup)
        os.chmod(current_backup, 0o600)
    data = _canonical(payload)
    _atomic_write(target_path, data, mode=mode, uid=uid, gid=gid)
    rollback_record = {
        "rolled_back_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "target": str(target_path),
        "restored_from": str(backup),
        "pre_rollback_backup": str(current_backup) if current_backup.exists() else None,
        "sha256": _sha256(data),
        "restart_required": True,
        "preserved_mode": oct(mode),
        "preserved_uid": uid,
        "preserved_gid": gid,
    }
    _atomic_write(state / "last-rollback.json", _canonical(rollback_record))
    return rollback_record
