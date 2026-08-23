#!/usr/bin/env python3
"""Fixed typed handlers for privileged Edge1 Operations API actions.

The unprivileged Operations API performs policy, precondition and application-health
checks. Privileged process control is delegated over one fixed Unix socket to the
separately sandboxed root broker.
"""
from __future__ import annotations

import hashlib
import json
import re
import socket
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

REPO = Path("/opt/edge1-management-interface")
SOURCE = REPO / "server" / "telephony_status_server.py"
SERVICE = "wwcx-telephony-console.service"
ASTERISK_SERVICE = "asterisk.service"
MESSAGING_SERVICE = "wwcx-messaging-gateway.service"
HEALTH_URL = "http://127.0.0.1:8096/healthz"
BROKER_SOCKET = "/run/edge1-operator-privileged/control.sock"
BROKER_MAX_RESPONSE = 8192
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
    if not isinstance(parameters, dict):
        raise TypedActionValidationError("telephony reload parameters must be an object")
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
    return dict(parameters)


def _broker_reload(parameters: dict[str, Any], request_id: str) -> dict[str, Any]:
    request = {
        "version": 1,
        "action": "telephony_console_reload",
        "request_id": request_id,
        "expected_pid": parameters["expected_pid"],
        "expected_source_sha256": parameters["expected_source_sha256"],
        "expected_repo_head": parameters["expected_repo_head"],
    }
    encoded = (json.dumps(request, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(30)
    try:
        sock.connect(BROKER_SOCKET)
        sock.sendall(encoded)
        sock.shutdown(socket.SHUT_WR)
        chunks = bytearray()
        while len(chunks) <= BROKER_MAX_RESPONSE:
            chunk = sock.recv(min(4096, BROKER_MAX_RESPONSE + 1 - len(chunks)))
            if not chunk:
                break
            chunks.extend(chunk)
            if b"\n" in chunk:
                break
    except (OSError, TimeoutError) as exc:
        raise RuntimeError("privileged broker is unavailable") from exc
    finally:
        sock.close()
    if not chunks or len(chunks) > BROKER_MAX_RESPONSE:
        raise RuntimeError("privileged broker returned an invalid response")
    try:
        response = json.loads(bytes(chunks).split(b"\n", 1)[0].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("privileged broker returned invalid JSON") from exc
    if not isinstance(response, dict) or response.get("status") != "succeeded":
        raise RuntimeError("privileged broker denied or failed the fixed action")
    if response.get("action") != "telephony_console_reload" or response.get("request_id") != request_id:
        raise RuntimeError("privileged broker response correlation failed")
    return response


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
    if asterisk_pid_before <= 0 or messaging_pid_before <= 0:
        raise RuntimeError("PBX or Messaging PID is unavailable")

    broker_request_id = "ops-" + uuid.uuid4().hex
    broker = _broker_reload(p, broker_request_id)

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
        asterisk_pid_after == asterisk_pid_before
        and messaging_pid_after == messaging_pid_before
    )
    broker_pid_after = broker.get("pid_after")

    if (
        not healthy
        or pid_after <= 0
        or pid_after == pid_before
        or broker_pid_after != pid_after
        or not unchanged_dependencies
    ):
        # Attempt one recovery restart of the same fixed reviewed unit through the
        # same narrow broker. This is not exposed as a second public capability.
        recovery = dict(p)
        recovery["expected_pid"] = pid_after if pid_after > 0 else int(broker_pid_after or 0)
        if recovery["expected_pid"] > 0:
            try:
                _broker_reload(recovery, broker_request_id + "-recovery")
            except Exception:
                pass
        raise RuntimeError("Telephony Console post-reload verification failed; bounded recovery attempted")

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
        "privilege_broker": "fixed_unix_socket_v1",
        "broker_request_id": broker_request_id,
        "rollback_policy": "one_bounded_recovery_restart_same_reviewed_unit",
    }


TYPED_ACTION_VALIDATORS = {
    "telephony_console_reload": _validate_reload,
}
TYPED_ACTION_HANDLERS = {
    "telephony_console_reload": telephony_console_reload,
}


def validate_typed_handler(name: str, parameters: dict[str, Any]) -> dict[str, Any]:
    validator = TYPED_ACTION_VALIDATORS.get(name)
    if validator is None:
        raise TypedActionValidationError("unknown typed action handler")
    return validator(parameters)


def run_typed_handler(name: str, parameters: dict[str, Any]) -> dict[str, Any]:
    handler = TYPED_ACTION_HANDLERS.get(name)
    if handler is None:
        raise TypedActionValidationError("unknown typed action handler")
    return handler(parameters)
