#!/usr/bin/env python3
"""Read-only operator health summary for Edge1 managed components.

Prints a compact OK/WARN/FAIL table without exposing sensitive diagnostics.
Roadmap: "Improve error messages and operator-facing health summaries" and
"Present service state without exposing sensitive diagnostics."

Checks (all local, all read-only):
  - Private Library Search API on 127.0.0.1:8091 and its search mode
  - Time Authority API on 127.0.0.1:8092 and its summary endpoint
  - systemd unit/timer states for the managed components (when systemd exists)
  - repository worktree cleanliness

Exit code: 0 when nothing FAILs (WARNs allowed), 1 otherwise.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

OK, WARN, FAIL = "OK", "WARN", "FAIL"

UNITS = [
    ("edge1-private-library-search.service", "search wrapper service"),
    ("edge1-time-authority-collector.timer", "time authority collector timer"),
    ("edge1-time-authority-dashboard.service", "time authority dashboard"),
    ("bigbird-spamhaus-filter.timer", "spamhaus refresh timer"),
]


def fetch_json(url: str, timeout: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check_search_api() -> tuple[str, str]:
    try:
        payload = fetch_json(
            "http://127.0.0.1:8091/api/private-library/search?q=health&collection=operations&limit=1"
        )
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return WARN, "not reachable on 127.0.0.1:8091 (service not running?)"
    mode = payload.get("mode", "unknown")
    if mode == "live_direct":
        return OK, "mode=live_direct"
    if mode in ("live", "fixture", "fixture_fallback"):
        return WARN, f"mode={mode} (expected live_direct in production)"
    return FAIL, f"unexpected mode={mode}"


def check_time_authority() -> tuple[str, str]:
    try:
        payload = fetch_json("http://127.0.0.1:8092/api/time-authority/summary")
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return WARN, "not reachable on 127.0.0.1:8092 (dashboard not running?)"
    if isinstance(payload, dict) and payload:
        return OK, "summary endpoint responding"
    return FAIL, "summary endpoint returned empty/unexpected payload"


def check_unit(unit: str) -> tuple[str, str]:
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        return WARN, "systemd not available here"
    proc = subprocess.run(
        [systemctl, "is-active", unit], capture_output=True, text=True
    )
    state = proc.stdout.strip() or "unknown"
    if state == "active":
        return OK, "active"
    if state in ("inactive", "unknown"):
        return WARN, f"{state} (not installed or not started)"
    return FAIL, state


def check_worktree() -> tuple[str, str]:
    git = shutil.which("git")
    if git is None or not (ROOT / ".git").exists():
        return WARN, "not a git checkout"
    proc = subprocess.run(
        [git, "-C", str(ROOT), "status", "--short"], capture_output=True, text=True
    )
    dirty = [line for line in proc.stdout.splitlines() if line.strip()]
    if not dirty:
        return OK, "clean"
    return WARN, f"{len(dirty)} uncommitted change(s)"


def main() -> int:
    rows: list[tuple[str, str, str]] = []

    status, detail = check_search_api()
    rows.append(("private library search API", status, detail))

    status, detail = check_time_authority()
    rows.append(("time authority API", status, detail))

    for unit, label in UNITS:
        status, detail = check_unit(unit)
        rows.append((label, status, detail))

    status, detail = check_worktree()
    rows.append(("repository worktree", status, detail))

    width = max(len(name) for name, _, _ in rows)
    failed = False
    for name, status, detail in rows:
        if status == FAIL:
            failed = True
        print(f"{name.ljust(width)}  {status:<4}  {detail}")

    print()
    counts = {s: sum(1 for _, status, _ in rows if status == s) for s in (OK, WARN, FAIL)}
    print(f"summary: {counts[OK]} ok, {counts[WARN]} warn, {counts[FAIL]} fail")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
