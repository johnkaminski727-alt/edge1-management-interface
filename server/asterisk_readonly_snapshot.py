#!/usr/bin/env python3
"""Produce a bounded native Asterisk diagnostic snapshot.

This helper accepts no caller input. It is intended to run as the existing
`asterisk` service account, which already owns the local Asterisk control
socket. Only the fixed read-only CLI commands declared below are executed.
The sanitized result is written atomically to one fixed runtime path for the
bounded Edge1 Operations API to consume read-only.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT_PATH = Path("/run/edge1-asterisk-diagnostics/status.json")
PATH = "/usr/sbin:/usr/bin:/sbin:/bin"
MAX_OUTPUT = 12000
COMMAND_TIMEOUT_SECONDS = 15

COMMANDS = (
    ("core_uptime", ("asterisk", "-rx", "core show uptime")),
    ("core_channels", ("asterisk", "-rx", "core show channels")),
    ("pjsip_endpoints", ("asterisk", "-rx", "pjsip show endpoints")),
    ("pjsip_transports", ("asterisk", "-rx", "pjsip show transports")),
    ("pjsip_registrations", ("asterisk", "-rx", "pjsip show registrations")),
    ("modules", ("asterisk", "-rx", "module show")),
    ("http_status", ("asterisk", "-rx", "http show status")),
)

SECRET_PATTERNS = (
    re.compile(r"(?i)\b(password|passwd|secret|token|api[_ -]?key|private[_ -]?key|preshared[_ -]?key)\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)\b(authorization:)\s*\S+"),
)
LONG_VALUE = re.compile(r"\b[A-Za-z0-9+/=_-]{64,}\b")


def clean(value: str) -> str:
    text = value.replace("\x00", "")
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    text = LONG_VALUE.sub("[REDACTED-LONG-VALUE]", text)
    return text[-MAX_OUTPUT:]


def run_fixed(argv: tuple[str, ...], timeout: int = COMMAND_TIMEOUT_SECONDS) -> dict:
    executable = shutil.which(argv[0], path=PATH)
    if executable is None:
        return {
            "available": False,
            "status": "command_unavailable",
            "exit_code": None,
            "duration_ms": 0,
            "stdout": "",
            "stderr": "",
        }
    started = time.monotonic()
    try:
        result = subprocess.run(
            list(argv),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env={"PATH": PATH, "LANG": "C", "LC_ALL": "C"},
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "available": True,
            "status": "timed_out",
            "exit_code": None,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "stdout": clean(exc.stdout or ""),
            "stderr": clean(exc.stderr or ""),
        }
    return {
        "available": True,
        "status": "ok" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "stdout": clean(result.stdout),
        "stderr": clean(result.stderr),
    }


def build_snapshot() -> dict:
    checks = []
    for name, argv in COMMANDS:
        checks.append({"name": name, "argv_id": f"asterisk.{name}", **run_fixed(argv)})
    now = time.time()
    return {
        "contract": "wwcx.edge1-asterisk-readonly-snapshot.v1",
        "generated_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "generated_at_epoch": now,
        "read_only": True,
        "parameters_accepted": False,
        "command_ids": [f"asterisk.{name}" for name, _ in COMMANDS],
        "status": "ok" if checks and all(item["status"] == "ok" for item in checks) else "error",
        "checks": checks,
    }


def write_snapshot(snapshot: dict, path: Path = SNAPSHOT_PATH) -> None:
    parent = path.parent
    if parent.is_symlink():
        raise RuntimeError("Asterisk diagnostic snapshot directory must not be a symlink")
    if parent.resolve(strict=True) != SNAPSHOT_PATH.parent:
        raise RuntimeError("Asterisk diagnostic snapshot parent path drift")
    if path.is_symlink():
        raise RuntimeError("Asterisk diagnostic snapshot path must not be a symlink")

    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=".status.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            os.fchmod(handle.fileno(), 0o640)
            json.dump(snapshot, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def main() -> int:
    snapshot = build_snapshot()
    write_snapshot(snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
