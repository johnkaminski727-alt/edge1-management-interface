#!/usr/bin/env python3
"""Minimal root broker for fixed Edge1 Operator privileged actions.

The unprivileged Operations API may request exactly one fixed process-control action
over a local Unix socket. Caller identity, approved runtime, exact preconditions and
root-side audit are all revalidated here before mutation.
"""
from __future__ import annotations

import grp
import hashlib
import json
import os
import pwd
import re
import socket
import stat
import struct
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOCKET_PATH = Path("/run/edge1-operator-privileged/control.sock")
AUDIT_PATH = Path("/var/lib/edge1-operator-privileged/audit.jsonl")
APPROVAL_PATH = Path("/etc/wwcx-edge1-operator/telephony-console-control.json")
ALLOWED_USER = "wwadmin"
ALLOWED_GROUP = "wwadmin"
ALLOWED_CGROUP = "edge1-operations-api.service"
REPO = Path("/opt/edge1-management-interface")
SOURCE_REL = "server/telephony_status_server.py"
SOURCE = REPO / SOURCE_REL
TELEPHONY_SERVICE = "wwcx-telephony-console.service"
ASTERISK_SERVICE = "asterisk.service"
MESSAGING_SERVICE = "wwcx-messaging-gateway.service"
MAX_REQUEST = 8192
MAX_RESPONSE = 8192
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")


class BrokerRequestError(ValueError):
    pass


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(argv: list[str], timeout: float = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
    )


def _value(argv: list[str]) -> str:
    result = _run(argv, timeout=5)
    return result.stdout.strip() if result.returncode == 0 else ""


def _pid(service: str) -> int:
    raw = _value(["systemctl", "show", service, "-p", "MainPID", "--value"])
    return int(raw) if raw.isdigit() else 0


def _active(service: str) -> bool:
    return _run(["systemctl", "is-active", "--quiet", service], timeout=5).returncode == 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_matches_head() -> bool:
    tracked = _run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", SOURCE_REL], timeout=5)
    clean = _run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", SOURCE_REL], timeout=5)
    return tracked.returncode == 0 and clean.returncode == 0


def _load_approved_runtime() -> dict[str, Any]:
    try:
        st = APPROVAL_PATH.stat()
    except OSError as exc:
        raise RuntimeError("approved Telephony runtime marker is unavailable") from exc
    if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or (st.st_mode & 0o022):
        raise RuntimeError("approved Telephony runtime marker permissions are unsafe")
    if st.st_size < 2 or st.st_size > 4096:
        raise RuntimeError("approved Telephony runtime marker size is invalid")
    try:
        value = json.loads(APPROVAL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("approved Telephony runtime marker is invalid") from exc
    expected = {"version", "service", "repo_head", "source_sha256"}
    if not isinstance(value, dict) or set(value) != expected:
        raise RuntimeError("approved Telephony runtime marker fields are invalid")
    if value["version"] != 1 or value["service"] != TELEPHONY_SERVICE:
        raise RuntimeError("approved Telephony runtime marker target is invalid")
    if not isinstance(value["repo_head"], str) or not HEX40.fullmatch(value["repo_head"]):
        raise RuntimeError("approved Telephony runtime commit is invalid")
    if not isinstance(value["source_sha256"], str) or not HEX64.fullmatch(value["source_sha256"]):
        raise RuntimeError("approved Telephony runtime digest is invalid")
    return value


def _validate_request(value: Any) -> dict[str, Any]:
    expected = {
        "version",
        "action",
        "request_id",
        "expected_pid",
        "expected_source_sha256",
        "expected_repo_head",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise BrokerRequestError("request fields do not match protocol")
    if value["version"] != 1 or value["action"] != "telephony_console_reload":
        raise BrokerRequestError("unsupported privileged action")
    if not isinstance(value["request_id"], str) or not REQUEST_ID.fullmatch(value["request_id"]):
        raise BrokerRequestError("invalid request_id")
    if not isinstance(value["expected_pid"], int) or isinstance(value["expected_pid"], bool) or value["expected_pid"] <= 0:
        raise BrokerRequestError("invalid expected_pid")
    if not isinstance(value["expected_source_sha256"], str) or not HEX64.fullmatch(value["expected_source_sha256"]):
        raise BrokerRequestError("invalid expected_source_sha256")
    if not isinstance(value["expected_repo_head"], str) or not HEX40.fullmatch(value["expected_repo_head"]):
        raise BrokerRequestError("invalid expected_repo_head")
    return dict(value)


def _peer_credentials(conn: socket.socket) -> tuple[int, int, int]:
    raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    return struct.unpack("3i", raw)


def _peer_is_operations_api(pid: int, uid: int) -> bool:
    if uid != pwd.getpwnam(ALLOWED_USER).pw_uid or pid <= 1:
        return False
    try:
        cgroup = Path(f"/proc/{pid}/cgroup").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(
        line.rstrip().endswith(f"/system.slice/{ALLOWED_CGROUP}")
        or line.rstrip().endswith(f"/{ALLOWED_CGROUP}")
        for line in cgroup.splitlines()
    )


def _audit(record: dict[str, Any]) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(AUDIT_PATH, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def _audit_best_effort(record: dict[str, Any]) -> None:
    try:
        _audit(record)
    except Exception:
        pass


def _execute_reload(request: dict[str, Any]) -> dict[str, Any]:
    if not SOURCE.is_file() or not _source_matches_head():
        raise RuntimeError("Telephony source is unavailable or differs from HEAD")
    if not _active(TELEPHONY_SERVICE):
        raise RuntimeError("telephony console inactive")
    if not _active(ASTERISK_SERVICE) or not _active(MESSAGING_SERVICE):
        raise RuntimeError("dependency inactive")

    telephony_pid_before = _pid(TELEPHONY_SERVICE)
    asterisk_pid_before = _pid(ASTERISK_SERVICE)
    messaging_pid_before = _pid(MESSAGING_SERVICE)
    source_sha256 = _sha256(SOURCE)
    repo_head = _value(["git", "-C", str(REPO), "rev-parse", "HEAD"])
    approved = _load_approved_runtime()

    if telephony_pid_before != request["expected_pid"]:
        raise RuntimeError("pid precondition changed")
    if source_sha256 != request["expected_source_sha256"]:
        raise RuntimeError("source precondition changed")
    if repo_head != request["expected_repo_head"]:
        raise RuntimeError("repository precondition changed")
    if approved["repo_head"] != repo_head or approved["source_sha256"] != source_sha256:
        raise RuntimeError("current Telephony source is not the approved runtime")
    if asterisk_pid_before <= 0 or messaging_pid_before <= 0:
        raise RuntimeError("dependency pid unavailable")

    restarted = _run(["systemctl", "restart", TELEPHONY_SERVICE], timeout=20)
    if restarted.returncode != 0:
        raise RuntimeError("telephony console restart failed")

    active = False
    for _ in range(10):
        if _active(TELEPHONY_SERVICE):
            active = True
            break
        time.sleep(0.5)

    telephony_pid_after = _pid(TELEPHONY_SERVICE)
    asterisk_pid_after = _pid(ASTERISK_SERVICE)
    messaging_pid_after = _pid(MESSAGING_SERVICE)
    if not active or telephony_pid_after <= 0 or telephony_pid_after == telephony_pid_before:
        raise RuntimeError("telephony console process did not rotate cleanly")
    if asterisk_pid_after != asterisk_pid_before or messaging_pid_after != messaging_pid_before:
        raise RuntimeError("dependency process changed unexpectedly")

    return {
        "version": 1,
        "action": "telephony_console_reload",
        "request_id": request["request_id"],
        "status": "succeeded",
        "pid_before": telephony_pid_before,
        "pid_after": telephony_pid_after,
        "approved_runtime": True,
        "asterisk_pid_unchanged": True,
        "messaging_pid_unchanged": True,
        "configuration_changed": False,
        "traffic_generated": False,
    }


def _receive_request(conn: socket.socket) -> dict[str, Any]:
    chunks = bytearray()
    while len(chunks) <= MAX_REQUEST:
        chunk = conn.recv(min(4096, MAX_REQUEST + 1 - len(chunks)))
        if not chunk:
            break
        chunks.extend(chunk)
        if b"\n" in chunk:
            break
    if not chunks or len(chunks) > MAX_REQUEST:
        raise BrokerRequestError("request size is invalid")
    line = bytes(chunks).split(b"\n", 1)[0]
    try:
        value = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BrokerRequestError("request is not valid JSON") from exc
    return _validate_request(value)


def _send(conn: socket.socket, payload: dict[str, Any]) -> None:
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(data) > MAX_RESPONSE:
        data = b'{"version":1,"status":"error","error":"response_too_large"}\n'
    conn.sendall(data)


def _audit_record(started: str, request_id: str, pid: int, uid: int, gid: int, status: str, error: str | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "schema": "wwcx.edge1-operator-privileged.audit.v1",
        "started_at": started,
        "recorded_at": utcnow(),
        "request_id": request_id,
        "action": "telephony_console_reload",
        "peer_pid": pid,
        "peer_uid": uid,
        "peer_gid": gid,
        "status": status,
        "error": error,
        **extra,
    }


def _serve_connection(conn: socket.socket) -> None:
    started = utcnow()
    pid = uid = gid = -1
    request_id = "unknown"
    try:
        pid, uid, gid = _peer_credentials(conn)
        if not _peer_is_operations_api(pid, uid):
            raise BrokerRequestError("peer is not the Operations API")
        request = _receive_request(conn)
        request_id = request["request_id"]
        _audit(_audit_record(started, request_id, pid, uid, gid, "authorized_attempt"))
        result = _execute_reload(request)
        _audit(_audit_record(
            started,
            request_id,
            pid,
            uid,
            gid,
            "succeeded",
            pid_before=result["pid_before"],
            pid_after=result["pid_after"],
        ))
        _send(conn, result)
    except BrokerRequestError:
        _audit_best_effort(_audit_record(started, request_id, pid, uid, gid, "denied", "request_denied"))
        _send(conn, {"version": 1, "status": "error", "error": "request_denied"})
    except Exception:
        _audit_best_effort(_audit_record(started, request_id, pid, uid, gid, "failed", "action_failed"))
        _send(conn, {"version": 1, "status": "error", "error": "action_failed", "request_id": request_id})


def _prepare_socket() -> socket.socket:
    SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    try:
        existing = SOCKET_PATH.lstat()
    except FileNotFoundError:
        pass
    else:
        if not stat.S_ISSOCK(existing.st_mode) or existing.st_uid != 0:
            raise RuntimeError("refusing to replace unexpected privileged broker socket path")
        SOCKET_PATH.unlink()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(SOCKET_PATH))
    os.chown(SOCKET_PATH, 0, grp.getgrnam(ALLOWED_GROUP).gr_gid)
    os.chmod(SOCKET_PATH, 0o660)
    server.listen(8)
    return server


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("privileged broker must run as root")
    server = _prepare_socket()
    try:
        while True:
            conn, _ = server.accept()
            with conn:
                conn.settimeout(10)
                _serve_connection(conn)
    finally:
        server.close()
        try:
            SOCKET_PATH.unlink()
        except FileNotFoundError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
