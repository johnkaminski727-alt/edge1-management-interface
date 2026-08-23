#!/usr/bin/env python3
"""Return sanitized preconditions for bounded Telephony Console control."""
from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path

REPO = Path("/opt/edge1-management-interface")
SOURCE = REPO / "server" / "telephony_status_server.py"
SERVICE = "wwcx-telephony-console.service"
HEALTH_URL = "http://127.0.0.1:8096/healthz"


def _run(argv: list[str]) -> str:
    result = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=5)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        "loopback_health": _health(),
        "control": "telephony_console_reload",
        "mutates_asterisk": False,
        "mutates_messaging_gateway": False,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), sort_keys=True))
