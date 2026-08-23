#!/usr/bin/env python3
"""Loopback-only, allowlisted Edge1 operations API.

No arbitrary command, path, SQL, service, or HTTP target is accepted from a
request. Requests are authenticated with HMAC-SHA256 and replay protected.
"""
import argparse
import hashlib
import hmac
import json
import os
import sqlite3
import subprocess
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from server.edge1_operations_typed_actions import (
    TypedActionValidationError,
    run_typed_handler,
)


def _configured_absolute_path(value):
    """Return an absolute path without resolving a deploy-time symlink target."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return Path(os.path.abspath(str(path)))


ROOT_CONFIGURED = _configured_absolute_path(os.environ.get("EDGE1_OPS_ROOT", "/opt/edge1-management-interface"))
ROOT = ROOT_CONFIGURED.resolve()
ALLOWLIST_PATH = Path(os.environ.get("EDGE1_OPS_ALLOWLIST", str(ROOT / "config/edge1-operations-allowlist.json")))
DB_PATH = Path(os.environ.get("EDGE1_OPS_DB", "/var/lib/edge1-operations-api/audit.sqlite3"))
SECRET_FILE = Path(os.environ.get("EDGE1_OPS_SECRET_FILE", "/etc/edge1-operations-api.secret"))
MUTATIONS_ENABLED = os.environ.get("EDGE1_OPS_MUTATIONS_ENABLED", "false").lower() == "true"
MUTATION_GATE_ENV = {
    "telephony_safe_controls": "EDGE1_OPS_TELEPHONY_SAFE_CONTROLS_ENABLED",
}
MAX_BODY = 16384
MAX_CLOCK_SKEW = 300


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def _gate_enabled(name):
    env_name = MUTATION_GATE_ENV.get(name)
    if env_name is None:
        raise ValueError("unknown mutation gate")
    return os.environ.get(env_name, "false").lower() == "true"


def ensure_root_stable():
    """Fail closed if a release/symlink switch changed the configured repo target."""
    try:
        current = ROOT_CONFIGURED.resolve(strict=True)
    except OSError as exc:
        raise RuntimeError("repository root is unavailable; service restart required") from exc
    if current != ROOT:
        raise RuntimeError("repository root target changed since service start; service restart required")
    return ROOT


def load_allowlist():
    ensure_root_stable()
    with ALLOWLIST_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    actions = data.get("actions", {})
    if not isinstance(actions, dict):
        raise ValueError("allowlist actions must be an object")
    return actions


def read_secret():
    value = SECRET_FILE.read_bytes().strip()
    if len(value) < 32:
        raise ValueError("secret must contain at least 32 bytes")
    return value


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS operation_audit (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            request_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            exit_code INTEGER,
            duration_ms INTEGER,
            stdout TEXT NOT NULL DEFAULT '',
            stderr TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS request_nonces (
            nonce TEXT PRIMARY KEY,
            created_at INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS operation_idempotency (
            action TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            request_hash TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (action, idempotency_key)
        )
    """)
    conn.commit()
    return conn


def record_audit(actor, action, body_hash, status, exit_code=None, duration_ms=None, stdout="", stderr=""):
    event_id = str(uuid.uuid4())
    with connect_db() as conn:
        conn.execute(
            "INSERT INTO operation_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, utcnow(), actor, action, body_hash, status, exit_code, duration_ms,
             stdout[-12000:], stderr[-12000:]),
        )
    return event_id


def check_and_store_nonce(nonce, timestamp):
    cutoff = int(time.time()) - MAX_CLOCK_SKEW
    with connect_db() as conn:
        conn.execute("DELETE FROM request_nonces WHERE created_at < ?", (cutoff,))
        try:
            conn.execute("INSERT INTO request_nonces VALUES (?, ?)", (nonce, timestamp))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def authenticate(headers, method, path, body):
    actor = headers.get("X-WWCX-Actor", "").strip()
    nonce = headers.get("X-WWCX-Nonce", "").strip()
    timestamp_text = headers.get("X-WWCX-Timestamp", "").strip()
    supplied = headers.get("X-WWCX-Signature", "").strip().lower()
    if not actor or not nonce or not timestamp_text or not supplied:
        return False, "missing authentication headers", ""
    try:
        timestamp = int(timestamp_text)
    except ValueError:
        return False, "invalid timestamp", actor
    if abs(int(time.time()) - timestamp) > MAX_CLOCK_SKEW:
        return False, "timestamp outside allowed window", actor
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((method, path, timestamp_text, nonce, actor, body_hash)).encode()
    expected = hmac.new(read_secret(), canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        return False, "invalid signature", actor
    if not check_and_store_nonce(nonce, timestamp):
        return False, "replayed nonce", actor
    return True, body_hash, actor


def _action_config(name):
    ensure_root_stable()
    action = load_allowlist().get(name)
    if not action:
        raise KeyError("unknown action")
    if not isinstance(action, dict):
        raise ValueError("invalid action configuration")
    return action


def safe_action(name):
    action = _action_config(name)
    if "typed_handler" in action:
        raise ValueError("typed action must use typed execution path")
    if "mutation_gate" in action:
        raise ValueError("fixed argv actions cannot declare dedicated mutation gates")
    argv = action.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
        raise ValueError("invalid action argv")
    mutating = bool(action.get("mutating", False))
    if mutating and not MUTATIONS_ENABLED:
        raise PermissionError("legacy mutating actions are disabled")
    cwd = Path(action.get("cwd", str(ROOT))).resolve()
    if cwd != ROOT and ROOT not in cwd.parents:
        raise ValueError("action cwd escapes repository root")
    timeout = int(action.get("timeout_seconds", 120))
    if timeout < 1 or timeout > 900:
        raise ValueError("invalid action timeout")
    return argv, cwd, timeout, mutating


def safe_typed_action(name):
    action = _action_config(name)
    handler = action.get("typed_handler")
    if not isinstance(handler, str) or not handler or "argv" in action or "cwd" in action:
        raise ValueError("invalid typed action configuration")
    mutating = bool(action.get("mutating", False))
    gate = action.get("mutation_gate")
    if mutating:
        if not isinstance(gate, str) or not gate:
            raise ValueError("typed mutating action requires a dedicated mutation gate")
        if not _gate_enabled(gate):
            raise PermissionError(f"mutation gate {gate} is disabled")
    elif gate is not None:
        raise ValueError("read-only typed action cannot declare mutation gate")
    timeout = int(action.get("timeout_seconds", 120))
    if timeout < 1 or timeout > 900:
        raise ValueError("invalid action timeout")
    return handler, timeout, mutating


def run_action(name, actor, body_hash):
    argv, cwd, timeout, _ = safe_action(name)
    ensure_root_stable()
    started = time.monotonic()
    try:
        result = subprocess.run(
            argv, cwd=str(cwd), text=True, capture_output=True,
            timeout=timeout, check=False, env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
        )
        duration = int((time.monotonic() - started) * 1000)
        status = "succeeded" if result.returncode == 0 else "failed"
        event_id = record_audit(actor, name, body_hash, status, result.returncode, duration,
                                result.stdout, result.stderr)
        return {
            "event_id": event_id,
            "action": name,
            "status": status,
            "exit_code": result.returncode,
            "duration_ms": duration,
            "stdout": result.stdout[-12000:],
            "stderr": result.stderr[-12000:],
        }
    except subprocess.TimeoutExpired as exc:
        duration = int((time.monotonic() - started) * 1000)
        event_id = record_audit(actor, name, body_hash, "timed_out", None, duration,
                                exc.stdout or "", exc.stderr or "")
        return {"event_id": event_id, "action": name, "status": "timed_out", "duration_ms": duration}


def _idempotency_lookup(action, key, request_hash):
    with connect_db() as conn:
        row = conn.execute(
            "SELECT request_hash, response_json FROM operation_idempotency WHERE action = ? AND idempotency_key = ?",
            (action, key),
        ).fetchone()
    if row is None:
        return None
    if row[0] != request_hash:
        raise TypedActionValidationError("idempotency key was already used with different parameters")
    payload = json.loads(row[1])
    payload["idempotent_replay"] = True
    return payload


def _idempotency_store(action, key, request_hash, response):
    with connect_db() as conn:
        conn.execute(
            "INSERT INTO operation_idempotency (action, idempotency_key, request_hash, response_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (action, key, request_hash, json.dumps(response, sort_keys=True), utcnow()),
        )
        conn.commit()


def run_typed_action(name, actor, body_hash, parameters):
    handler, timeout, _ = safe_typed_action(name)
    if not isinstance(parameters, dict):
        raise TypedActionValidationError("typed action body must be a JSON object")
    key = parameters.get("idempotency_key")
    if not isinstance(key, str):
        raise TypedActionValidationError("typed action requires idempotency_key")
    replay = _idempotency_lookup(name, key, body_hash)
    if replay is not None:
        return replay

    started = time.monotonic()
    try:
        result_payload = run_typed_handler(handler, parameters)
        duration = int((time.monotonic() - started) * 1000)
        if duration > timeout * 1000:
            raise RuntimeError("typed action exceeded configured timeout")
        response = {
            "action": name,
            "status": "succeeded",
            "exit_code": 0,
            "duration_ms": duration,
            "result": result_payload,
            "idempotent_replay": False,
        }
        event_id = record_audit(actor, name, body_hash, "succeeded", 0, duration,
                                json.dumps(result_payload, sort_keys=True), "")
        response["event_id"] = event_id
        _idempotency_store(name, key, body_hash, response)
        return response
    except TypedActionValidationError:
        raise
    except Exception as exc:
        duration = int((time.monotonic() - started) * 1000)
        event_id = record_audit(actor, name, body_hash, "failed", 1, duration, "", str(exc))
        response = {
            "event_id": event_id,
            "action": name,
            "status": "failed",
            "exit_code": 1,
            "duration_ms": duration,
            "error": "typed action failed verification",
            "idempotent_replay": False,
        }
        _idempotency_store(name, key, body_hash, response)
        return response


class Handler(BaseHTTPRequestHandler):
    server_version = "Edge1OperationsAPI/2"

    def send_json(self, status, payload):
        encoded = json.dumps(payload, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, fmt, *args):
        return

    def read_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("invalid content length")
        if length < 0 or length > MAX_BODY:
            raise ValueError("request body too large")
        return self.rfile.read(length)

    def do_GET(self):
        if self.path == "/healthz":
            try:
                actions = load_allowlist()
                connect_db().close()
                self.send_json(200, {
                    "status": "ok",
                    "actions": len(actions),
                    "mutations_enabled": MUTATIONS_ENABLED,
                    "mutation_gates": {
                        name: _gate_enabled(name) for name in sorted(MUTATION_GATE_ENV)
                    },
                    "repository_root_stable": True,
                })
            except Exception as exc:
                self.send_json(503, {"status": "error", "detail": str(exc), "repository_root_stable": False})
            return
        if self.path == "/v1/actions":
            ok, detail, actor = authenticate(self.headers, "GET", self.path, b"")
            if not ok:
                self.send_json(401, {"error": detail})
                return
            try:
                actions = load_allowlist()
            except RuntimeError as exc:
                self.send_json(503, {"error": str(exc), "repository_root_stable": False})
                return
            self.send_json(200, {"actions": [
                {
                    "name": name,
                    "mutating": bool(value.get("mutating")),
                    "typed": isinstance(value.get("typed_handler"), str),
                    "mutation_gate": value.get("mutation_gate"),
                }
                for name, value in sorted(actions.items())
            ]})
            return
        self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/v1/actions/") or not self.path.endswith("/run"):
            self.send_json(404, {"error": "not found"})
            return
        try:
            body = self.read_body()
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
            return
        ok, detail, actor = authenticate(self.headers, "POST", self.path, body)
        if not ok:
            self.send_json(401, {"error": detail})
            return
        name = self.path[len("/v1/actions/"):-len("/run")].strip("/")
        try:
            action = _action_config(name)
            if "typed_handler" in action:
                try:
                    parameters = json.loads(body.decode("utf-8")) if body else {}
                except (UnicodeDecodeError, json.JSONDecodeError):
                    raise TypedActionValidationError("typed action body must be valid JSON")
                result = run_typed_action(name, actor, detail, parameters)
            else:
                if body not in (b"", b"{}", b"{}\n"):
                    self.send_json(400, {"error": "action parameters are not accepted"})
                    return
                result = run_action(name, actor, detail)
        except KeyError:
            self.send_json(404, {"error": "unknown action"})
            return
        except PermissionError as exc:
            event_id = record_audit(actor, name, detail, "denied", stderr=str(exc))
            self.send_json(403, {"error": str(exc), "event_id": event_id})
            return
        except TypedActionValidationError as exc:
            event_id = record_audit(actor, name, detail, "denied", stderr=str(exc))
            self.send_json(409, {"error": str(exc), "event_id": event_id})
            return
        except Exception as exc:
            event_id = record_audit(actor, name, detail, "error", stderr=str(exc))
            self.send_json(500, {"error": "action configuration error", "event_id": event_id})
            return
        self.send_json(200 if result["status"] == "succeeded" else 409, result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("EDGE1_OPS_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("EDGE1_OPS_PORT", "8097")))
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "::1"):
        raise SystemExit("refusing non-loopback bind")
    load_allowlist()
    read_secret()
    connect_db().close()
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
