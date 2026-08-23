#!/usr/bin/env python3
"""Fixed typed handlers for privileged Edge1 Operations API actions.

No handler accepts a command, path, service name, URL, or arbitrary argv from callers.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path("/opt/edge1-management-interface")
SOURCE = REPO / "server" / "telephony_status_server.py"
SERVICE = "wwcx-telephony-console.service"
ASTERISK_SERVICE = "asterisk.service"
MESSAGING_SERVICE = "wwcx-messaging-gateway.service"
HEALTH_URL = "http://127.0.0.1:8096/healthz"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
IDEMPOTENCY = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")


class TypedActionValidationError(ValueError):
    pass


def _run(argv: list[str], timeout: float = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False, timeout=timeout)


def _value(argv: list[str]) -> str:
    result = _run(argv)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _pid(service: str) -> int:
    raw = _value(["systemctl", "show", service, "-p", "MainPID", "--value"])
    return int(raw) if raw.isdigit() else 0


def _active(service: str) -> bool:
    return _run(["systemctl", "is-active", "--quiet", service]).returncode == 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _health() -> bool:
    try:
        request = urllib.request.Request(HEALTH_URL, headers={"User-Agent": "edge1-operations-api/telephony-control"})
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def _validate_reload(parameters: dict[str, Any]) -> dict[str, Any]:
    expected = {"expected_pid", "expected_source_sha256", "expected_repo_head", "idempotency_key"}
    if set(parameters) != expected:
        raise TypedActionValidationError("telephony reload parameters do not match the fixed schema")
    pid = parameters["expected_pid"]
    source_sha = parameters["expected_source_sha256"]
    repo_head = parameters["expected_repo_head"]
    key = parameters["idempotency_key"]
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        raise TypedActionValidationError("expected_pid must be a positive integer")
    if not isinstance(source_sha, str) or not HEX64.fullmatch(source_sha):
        raise TypedActionValidationError("expected_source_sha256 must be lowercase SHA-256")
    if not isinstance(repo_head, str) or not HEX40.fullmatch(repo_head):
        raise TypedActionValidationError("expected_repo_head must be a full lowercase commit SHA")
    if not isinstance(key, str) or not IDEMPOTENCY.fullmatch(key):
        raise TypedActionValidationError("idempotency_key format is invalid")
    return parameters


def telephony_console_reload(parameters: dict[str, Any]) -> dict[str, Any]:
    """Restart only the read-only Telephony Console after exact precondition checks."""
    p = _validate_reload(parameters)
    if not SOURCE.is_file():
        raise RuntimeError("reviewed Telephony Console source is unavailable")
    if not _active(SERVICE):
        raise RuntimeError("Telephony Console is not active")
    if not _active(ASTERISK_SERVICE) or not _active(MESSAGING_SERVICE):
        raise RuntimeError("PBX or Messaging prerequisite is not active")

    pid_before = _pid(SERVICE)
    asterisk_pid_before = _pid(ASTERISK_SERVICE)
    messaging_pid_before = _pid(MESSAGING_SERVICE)
    source_sha = _sha256(SOURCE)
    repo_head = _value(["git", "-C", str(REPO), "rev-parse", "HEAD"])

    if pid_before != p["expected_pid"]:
        raise RuntimeError("Telephony Console PID precondition changed")
    if source_sha != p["expected_source_sha256"]:
        raise RuntimeError("Telephony Console source digest precondition changed")
    if repo_head != p["expected_repo_head"]:
        raise RuntimeError("repository HEAD precondition changed")

    restarted = _run(["systemctl", "restart", SERVICE], timeout=20)
    if restarted.returncode != 0:
        raise RuntimeError("Telephony Console restart failed")

    healthy = False
    for _ in range(10):
        if _active(SERVICE) and _health():
            healthy = True
            break
        time.sleep(1)

    pid_after = _pid(SERVICE)
    asterisk_pid_after = _pid(ASTERISK_SERVICE)
    messaging_pid_after = _pid(MESSAGING_SERVICE)
    unchanged_dependencies = (
        asterisk_pid_before > 0
        and messaging_pid_before > 0
        and asterisk_pid_after == asterisk_pid_before
        and messaging_pid_after == messaging_pid_before
    )

    if not healthy or pid_after <= 0 or pid_after == pid_before or not unchanged_dependencies:
        # No configuration was changed. A recovery restart of the same reviewed unit is
        # the only bounded rollback available for this process-generation mutation.
        _run(["systemctl", "restart", SERVICE], timeout=20)
        raise RuntimeError("Telephony Console post-reload verification failed; recovery restart attempted")

    return {
        "service": SERVICE,
        "status": "succeeded",
        "pid_before": pid_before,
        "pid_after": pid_after,
        "source_sha256": source_sha,
        "repo_head": repo_head,
        "loopback_health": True,
        "asterisk_pid_unchanged": True,
        "messaging_pid_unchanged": True,
        "configuration_changed": False,
        "traffic_generated": False,
        "rollback_policy": "recovery_restart_same_reviewed_unit",
    }


TYPED_ACTION_HANDLERS = {
    "telephony_console_reload": telephony_console_reload,
}


def run_typed_handler(name: str, parameters: dict[str, Any]) -> dict[str, Any]:
    handler = TYPED_ACTION_HANDLERS.get(name)
    if handler is None:
        raise TypedActionValidationError("unknown typed action handler")
    return handler(parameters)
