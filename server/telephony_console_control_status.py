#!/usr/bin/env python3
"""Return sanitized preconditions for bounded Telephony Console control."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import urllib.request
from pathlib import Path

REPO = Path("/opt/edge1-management-interface")
SOURCE_REL = "server/telephony_status_server.py"
SOURCE = REPO / SOURCE_REL
APPROVAL_PATH = Path("/etc/wwcx-edge1-operator/telephony-console-control.json")
SERVICE = "wwcx-telephony-console.service"
HEALTH_URL = "http://127.0.0.1:8096/healthz"


def _command(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False, timeout=5)


def _run(argv: list[str]) -> str:
    result = _command(argv)
    return result.stdout.strip() if result.returncode == 0 else ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_matches_head() -> bool:
    tracked = _command(["git", "-C", str(REPO), "ls-files", "--error-unmatch", SOURCE_REL])
    clean = _command(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", SOURCE_REL])
    return tracked.returncode == 0 and clean.returncode == 0


def _approved_runtime_matches(repo_head: str, source_sha256: str) -> bool:
    try:
        st = APPROVAL_PATH.stat()
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or (st.st_mode & 0o022) or st.st_size > 4096:
            return False
        value = json.loads(APPROVAL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(value, dict)
        and set(value) == {"version", "service", "repo_head", "source_sha256"}
        and value.get("version") == 1
        and value.get("service") == SERVICE
        and value.get("repo_head") == repo_head
        and value.get("source_sha256") == source_sha256
    )


def _health() -> bool:
    try:
        request = urllib.request.Request(HEALTH_URL, headers={"User-Agent": "edge1-operator-control/1"})
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def snapshot() -> dict[str, object]:
    active = _run(["systemctl", "is-active", SERVICE]) == "active"
    pid_text = _run(["systemctl", "show", SERVICE, "-p", "MainPID", "--value"])
    pid = int(pid_text) if pid_text.isdigit() else 0
    repo_head = _run(["git", "-C", str(REPO), "rev-parse", "HEAD"])
    source_sha256 = _sha256(SOURCE) if SOURCE.is_file() else ""
    return {
        "service": SERVICE,
        "active": active,
        "pid": pid,
        "repo_head": repo_head,
        "source_sha256": source_sha256,
        "source_matches_head": _source_matches_head(),
        "approved_runtime_matches": _approved_runtime_matches(repo_head, source_sha256),
        "loopback_health": _health(),
        "control": "telephony_console_reload",
        "mutates_asterisk": False,
        "mutates_messaging_gateway": False,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), sort_keys=True))
