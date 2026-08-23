#!/usr/bin/env python3
"""Synchronize WW.CX Ava admin-function desired state to the local operator broker."""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import secrets
import signal
import ssl
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

STOP = False
QUEUE_URL = os.environ.get("BB_QUEUE_URL", "").strip()
QUEUE_KEY_ID = os.environ.get("BB_QUEUE_KEY_ID", "").strip()
QUEUE_SECRET = os.environ.get("BB_QUEUE_SECRET", "").strip()
WORKER_ID = "ava-admin-functions-edge1"
BROKER_URL = "http://127.0.0.1:8118/invoke"
BROKER_TOKEN = Path("/etc/ava-operator/broker-token")
POLL_SECONDS = max(1.0, min(float(os.getenv("AVA_ADMIN_FUNCTIONS_POLL_SECONDS", "2")), 30.0))
SSL_CONTEXT = ssl.create_default_context()
HOST_MAP = {"edge1_shell": "edge1", "business159_shell": "business159"}


def log(event: str, **fields: Any) -> None:
    print(json.dumps({"time_unix": int(time.time()), "event": event, **fields}, separators=(",", ":"), sort_keys=True), flush=True)


def stop_handler(_sig: int, _frame: Any) -> None:
    global STOP
    STOP = True


signal.signal(signal.SIGTERM, stop_handler)
signal.signal(signal.SIGINT, stop_handler)


def validate_config() -> None:
    parsed = urllib.parse.urlsplit(QUEUE_URL)
    if parsed.scheme != "https" or parsed.hostname != "ww.cx" or not parsed.path:
        raise RuntimeError("BB_QUEUE_URL must use the approved WW.CX HTTPS endpoint")
    if not QUEUE_KEY_ID or len(QUEUE_SECRET) < 64:
        raise RuntimeError("queue signing configuration is incomplete")


def queue_post(payload: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    body_hash = hashlib.sha256(raw).hexdigest()
    path = urllib.parse.urlsplit(QUEUE_URL).path or "/"
    canonical = f"POST\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
    signature = hmac.new(QUEUE_SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    request = urllib.request.Request(QUEUE_URL, data=raw, method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "ava-admin-functions-sync/1",
        "X-BB-Worker-Key-Id": QUEUE_KEY_ID, "X-BB-Timestamp": timestamp,
        "X-BB-Nonce": nonce, "X-BB-Body-SHA256": body_hash, "X-BB-Signature": signature,
    })
    try:
        response = urllib.request.urlopen(request, timeout=15, context=SSL_CONTEXT)
        status, body, headers = response.status, response.read(131073), response.headers
    except urllib.error.HTTPError as exc:
        status, body, headers = exc.code, exc.read(131073), exc.headers
    if len(body) > 131072:
        raise RuntimeError("queue response too large")
    response_timestamp = headers.get("X-BB-Response-Timestamp", "")
    response_hash = headers.get("X-BB-Response-Body-SHA256", "").lower()
    response_signature = headers.get("X-BB-Response-Signature", "").lower()
    actual_hash = hashlib.sha256(body).hexdigest()
    if not response_timestamp.isdigit() or abs(int(time.time()) - int(response_timestamp)) > 180:
        raise RuntimeError("queue response timestamp invalid")
    if not hmac.compare_digest(actual_hash, response_hash):
        raise RuntimeError("queue response body hash mismatch")
    expected = hmac.new(QUEUE_SECRET.encode(), f"{status}\n{response_timestamp}\n{nonce}\n{response_hash}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, response_signature):
        raise RuntimeError("queue response signature mismatch")
    value = json.loads(body.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("queue response is not an object")
    if status >= 400:
        raise RuntimeError(f"queue HTTP {status}: {value.get('error', 'request failed')}")
    return value


def broker_token() -> str:
    st = BROKER_TOKEN.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_mode & stat.S_IRWXO:
        raise RuntimeError("broker token permissions are unsafe")
    token = BROKER_TOKEN.read_text(encoding="utf-8").strip()
    if len(token) < 32 or any(ch.isspace() for ch in token):
        raise RuntimeError("broker token invalid")
    return token


def broker_call(capability: str, arguments: dict[str, Any] | None = None, *, confirmed: bool = False) -> dict[str, Any]:
    raw = json.dumps({"capability": capability, "arguments": arguments or {}, "confirmed": confirmed}, separators=(",", ":")).encode()
    request = urllib.request.Request(BROKER_URL, data=raw, method="POST", headers={"Authorization": f"Bearer {broker_token()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read(262145)
    if len(body) > 262144:
        raise RuntimeError("broker response too large")
    value = json.loads(body.decode("utf-8"))
    if not isinstance(value, dict) or value.get("status") != "completed":
        raise RuntimeError("broker rejected admin-function synchronization")
    return value


def reconcile_control(key: str, control: dict[str, Any]) -> dict[str, Any]:
    host = HOST_MAP[key]
    now = int(time.time())
    desired = control.get("desired_enabled") is True
    expiry = control.get("desired_expires_at") if isinstance(control.get("desired_expires_at"), int) else None
    generation = max(0, int(control.get("generation", 0)))
    actor = str(control.get("requested_by") or "ww.cx admin")[:128]
    if desired and (expiry is None or expiry <= now):
        desired = False
    current = broker_call("shell.gate.status", {"host": host}).get("result", {})
    current_enabled = isinstance(current, dict) and current.get("enabled") is True
    current_expiry = current.get("expires_at_unix") if isinstance(current, dict) else None
    current_generation = int(current.get("generation", 0) or 0) if isinstance(current, dict) else 0
    if desired != current_enabled or (desired and (current_expiry != expiry or current_generation != generation)):
        args = {"host": host, "enabled": desired, "expires_at_unix": expiry if desired else None, "actor": actor, "generation": generation}
        current = broker_call("shell.gate.set", args, confirmed=True).get("result", {})
    return {
        "function_key": key, "generation": generation,
        "observed_enabled": bool(isinstance(current, dict) and current.get("enabled") is True),
        "observed_expires_at": current.get("expires_at_unix") if isinstance(current, dict) and isinstance(current.get("expires_at_unix"), int) else None,
        "status": "ok", "error": "",
    }


def sync_once() -> list[dict[str, Any]]:
    state = queue_post({"action": "admin_functions", "worker_id": WORKER_ID})
    controls = state.get("controls")
    if not isinstance(controls, list):
        raise RuntimeError("admin function state missing")
    by_key = {str(item.get("function_key")): item for item in controls if isinstance(item, dict)}
    report: list[dict[str, Any]] = []
    for key in HOST_MAP:
        control = by_key.get(key, {"function_key": key, "desired_enabled": False, "generation": 0})
        try:
            report.append(reconcile_control(key, control))
        except Exception as exc:
            report.append({"function_key": key, "generation": max(0, int(control.get("generation", 0))), "observed_enabled": False, "observed_expires_at": None, "status": "error", "error": type(exc).__name__})
    queue_post({"action": "admin_functions_report", "worker_id": WORKER_ID, "controls": report})
    return report


def main() -> int:
    validate_config()
    log("admin_functions_sync_started")
    while not STOP:
        try:
            sync_once()
        except Exception as exc:
            log("admin_functions_sync_error", error_type=type(exc).__name__)
        deadline = time.monotonic() + POLL_SECONDS
        while not STOP and time.monotonic() < deadline:
            time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
