#!/usr/bin/env python3
"""Resolve the live Asterisk process without trusting SysV systemd MainPID alone."""
from __future__ import annotations

import subprocess
from pathlib import Path

ASTERISK_SERVICE = "asterisk.service"
PIDFILES = (Path("/run/asterisk/asterisk.pid"), Path("/var/run/asterisk/asterisk.pid"))


class AsteriskProcessIdentityError(RuntimeError):
    pass


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
    )


def _valid_pid(value: str | int) -> int | None:
    try:
        pid = int(value)
    except (TypeError, ValueError):
        return None
    if pid <= 1:
        return None
    try:
        comm = Path(f"/proc/{pid}/comm").read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    return pid if comm == "asterisk" else None


def resolve_asterisk_pid() -> tuple[int, str]:
    result = _run(["systemctl", "show", ASTERISK_SERVICE, "-p", "MainPID", "--value"])
    if result.returncode == 0:
        pid = _valid_pid(result.stdout.strip())
        if pid is not None:
            return pid, "systemd:MainPID"

    for pidfile in PIDFILES:
        try:
            first = pidfile.read_text(encoding="utf-8", errors="replace").splitlines()[0].split()[0]
        except (OSError, IndexError):
            continue
        pid = _valid_pid(first)
        if pid is not None:
            return pid, f"pidfile:{pidfile}"

    matches: list[int] = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        pid = _valid_pid(proc.name)
        if pid is None:
            continue
        try:
            argv = (proc / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if b"-f" in argv:
            matches.append(pid)
    if len(matches) == 1:
        return matches[0], "procfs:unique-asterisk-f"
    raise AsteriskProcessIdentityError("unable to resolve one validated Asterisk process")
