#!/usr/bin/env python3
"""Authenticated loopback broker that gives Ava typed Edge1/Business159 operator access.

The broker owns privileged transport access. Ava receives neither the Edge1 MCP bearer
secret nor Business159 SSH credentials. Raw shell exists only behind an explicit
confirmed request and is never advertised as a normal model tool.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import http.server
import json
import os
import re
import stat
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

try:
    from .ava_operator_policy import authorize, load_policy
except ImportError:
    from ava_operator_policy import authorize, load_policy

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8118
DEFAULT_TOKEN = Path("/etc/ava-operator/broker-token")
EDGE1_TOKEN = Path("/etc/edge1-operator/mcp-token")
EDGE1_OPERATOR_URL = "http://127.0.0.1:8102/mcp"
EDGE1_SHELL_URL = "http://127.0.0.1:8114/mcp"
BUSINESS159_SSH = "/usr/bin/ssh"
BUSINESS159_RUNUSER = "/usr/sbin/runuser"
BUSINESS159_USER = "business159-operator"
BUSINESS159_CONFIG = "/etc/business159-operator/ssh_config"
BUSINESS159_ALIAS = "business159"
AUDIT = Path("/var/log/wwcx-ava-operator-broker/audit.jsonl")
SHELL_GATE_DIR = Path(os.getenv("AVA_SHELL_GATE_DIR", "/var/lib/wwcx-ava-operator-broker/shell-gates"))
SHELL_HOSTS = {"edge1", "business159"}
MAX_BODY = 65536
MAX_OUTPUT = 131072

EDGE1_READ_TOOLS = {
    "edge1.read.health": "edge1.health",
    "edge1.read.identity": "edge1.identity",
    "edge1.read.snapshot": "edge1.snapshot",
    "edge1.read.inventory": "edge1.inventory",
    "edge1.read.services": "edge1.services",
    "edge1.read.network": "edge1.network_state",
    "edge1.read.disk": "edge1.disk_state",
    "edge1.read.bigbird": "edge1.bigbird_status",
    "edge1.read.operations": "edge1.operations_status",
    "edge1.read.git": "edge1.git_state",
    "edge1.read.config": "edge1.config_digest",
}

BUSINESS159_READ_COMMANDS = {
    "business159.read.health": "hostname -f; id -un; printf 'php='; php -r 'echo PHP_VERSION;' 2>/dev/null || true; printf '\\nrepo='; cd ~/apps/ww-cx-website && git rev-parse --short=12 HEAD; printf '\\nweb='; curl -fsS -o /dev/null -w '%{http_code}' https://ww.cx/ || true; printf '\\n'",
    "business159.read.identity": "hostname -f; id -un; pwd",
    "business159.read.git": "cd ~/apps/ww-cx-website && printf 'branch='; git branch --show-current; printf 'head='; git rev-parse HEAD; git status --short --branch; printf 'origin='; git remote get-url origin",
    "business159.read.deployment": "printf 'current='; readlink ~/current 2>/dev/null || true; printf '\\n'; tail -n 12 ~/shared/ww-cx-website/deployments.log 2>/dev/null || true",
    "business159.read.bridge": "f=~/wwcx-store-private/operations-center/latest.json; if [ -f \"$f\" ]; then stat -c 'size=%s mtime=%Y' \"$f\"; sha256sum \"$f\" | awk '{print \"sha256=\" $1}'; else echo missing; fi",
    "business159.read.config": "for f in ~/shared/ww-cx-website/config.env ~/apps/ww-cx-website/scripts/deploy-business159.sh ~/apps/ww-cx-website/scripts/validate.sh ~/public_html/.htaccess; do if [ -f \"$f\" ]; then printf '%s ' \"$f\"; sha256sum \"$f\" | awk '{print $1}'; else printf '%s missing\\n' \"$f\"; fi; done",
}

SAFE_SERVICES = {
    "bigbird-ai-gateway.service",
    "bigbird-ai-poller.service",
    "wwcx-ava-office.service",
    "edge1-operations-api.service",
    "edge1-operator-mcp.service",
    "business159-secure-mcp-tunnel.service",
    "edge1-agent-shell.service",
    "edge1-agent-shell-secure-mcp-tunnel.service",
}


def _private_token(path: Path) -> str:
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_mode & stat.S_IRWXO:
        raise RuntimeError(f"unsafe token permissions: {path}")
    value = path.read_text(encoding="utf-8").strip()
    if len(value) < 32 or any(ch.isspace() for ch in value):
        raise RuntimeError(f"invalid token: {path}")
    return value


def _audit(event: str, **fields: Any) -> None:
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    record = {"time_unix": int(time.time()), "event": event, **fields}
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")


def _decode_mcp_payload(raw: bytes, content_type: str = "") -> dict[str, Any]:
    text = raw.decode("utf-8")
    if not content_type.lower().startswith("text/event-stream"):
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("MCP response is not an object")
        return value
    data_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
        elif not line.strip() and data_lines:
            candidate = "\n".join(data_lines)
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
            data_lines = []
    if data_lines:
        value = json.loads("\n".join(data_lines))
        if isinstance(value, dict):
            return value
    raise ValueError("MCP event stream contained no JSON object")


def _mcp(url: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": arguments}}, separators=(",", ":")).encode()
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {_private_token(EDGE1_TOKEN)}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    })
    try:
        with urllib.request.urlopen(request, timeout=130) as response:
            raw = response.read(MAX_OUTPUT + 1)
            if len(raw) > MAX_OUTPUT:
                raise RuntimeError("Edge1 operator response too large")
            payload = _decode_mcp_payload(raw, response.headers.get("Content-Type", ""))
    except (urllib.error.URLError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError("Edge1 operator transport unavailable") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("result"), dict):
        raise RuntimeError("Edge1 operator returned invalid response")
    result = payload["result"]
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    content = result.get("content")
    if isinstance(content, list) and content and isinstance(content[0], dict):
        text = content[0].get("text")
        if isinstance(text, str):
            try:
                decoded = json.loads(text)
                if isinstance(decoded, dict):
                    return decoded
            except json.JSONDecodeError:
                pass
    raise RuntimeError("Edge1 operator returned no structured result")


def shell_gate_status(host: str) -> dict[str, Any]:
    if host not in SHELL_HOSTS:
        raise ValueError("unknown shell host")
    path = SHELL_GATE_DIR / f"{host}.json"
    now = int(time.time())
    try:
        st = path.stat()
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise RuntimeError("shell gate permissions are unsafe")
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"host": host, "enabled": False, "reason": "not_enabled"}
    except (OSError, json.JSONDecodeError) as exc:
        return {"host": host, "enabled": False, "reason": "invalid_gate", "error_type": type(exc).__name__}
    expires = value.get("expires_at_unix")
    if not isinstance(expires, int) or expires <= now:
        return {"host": host, "enabled": False, "reason": "expired", "expires_at_unix": expires if isinstance(expires, int) else None}
    return {
        "host": host,
        "enabled": True,
        "reason": "enabled",
        "expires_at_unix": expires,
        "remaining_seconds": max(0, expires - now),
        "actor": str(value.get("actor", ""))[:128],
        "ticket": str(value.get("ticket", ""))[:128],
        "source": str(value.get("source", ""))[:128],
        "generation": max(0, int(value.get("generation", 0))) if str(value.get("generation", "0")).isdigit() else 0,
    }


def set_shell_gate(host: str, *, enabled: bool, expires_at_unix: int | None, actor: str, generation: int = 0) -> dict[str, Any]:
    if host not in SHELL_HOSTS:
        raise ValueError("unknown shell host")
    SHELL_GATE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(SHELL_GATE_DIR, 0o700)
    path = SHELL_GATE_DIR / f"{host}.json"
    if not enabled:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return shell_gate_status(host)
    now = int(time.time())
    if not isinstance(expires_at_unix, int) or expires_at_unix <= now or expires_at_unix > now + 14400:
        raise ValueError("shell gate expiry must be within the next 240 minutes")
    actor = actor.strip()[:128]
    if not actor:
        raise ValueError("shell gate actor is required")
    value = {
        "version": 2, "host": host, "enabled_at_unix": now,
        "expires_at_unix": expires_at_unix, "actor": actor,
        "ticket": "admin-functions", "source": "wwcx-admin-functions",
        "generation": max(0, int(generation)),
    }
    tmp = path.with_name(f".{host}.{uuid.uuid4().hex}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, separators=(",", ":"), sort_keys=True)
            handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, path); os.chmod(path, 0o600)
    finally:
        try: tmp.unlink()
        except FileNotFoundError: pass
    return shell_gate_status(host)


def _business159(command: str, *, timeout: int = 30) -> dict[str, Any]:
    if len(command) > 4000:
        raise ValueError("Business159 command too long")
    wrapped = "set -eu; test \"$(hostname -f)\" = business159.web-hosting.com; test \"$(id -un)\" = wwcxjywl; " + command
    proc = subprocess.run(
        [BUSINESS159_RUNUSER, "-u", BUSINESS159_USER, "--", BUSINESS159_SSH, "-F", BUSINESS159_CONFIG, BUSINESS159_ALIAS, wrapped],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    stdout = proc.stdout[:MAX_OUTPUT].decode("utf-8", errors="replace")
    stderr = proc.stderr[:16384].decode("utf-8", errors="replace")
    return {"ok": proc.returncode == 0, "exit_code": proc.returncode, "stdout": stdout, "stderr": stderr}


def invoke(capability: str, arguments: dict[str, Any], confirmed: bool) -> dict[str, Any]:
    policy = load_policy()
    decision = authorize(capability, confirmed=confirmed, policy=policy)
    request_id = str(uuid.uuid4())
    if not decision["allowed"]:
        _audit("denied", request_id=request_id, capability=capability, classification=decision["classification"], reason=decision["reason"])
        return {"request_id": request_id, "status": "denied", "decision": decision}

    if capability == "shell.gate.status":
        host = str(arguments.get("host", ""))
        try:
            result = shell_gate_status(host)
        except ValueError as exc:
            return {"request_id": request_id, "status": "error", "decision": decision, "error": str(exc)}
        return {"request_id": request_id, "status": "completed", "decision": decision, "result": result}

    if capability == "shell.gate.set":
        host = str(arguments.get("host", ""))
        try:
            result = set_shell_gate(host, enabled=bool(arguments.get("enabled", False)), expires_at_unix=arguments.get("expires_at_unix"), actor=str(arguments.get("actor", "")), generation=int(arguments.get("generation", 0)))
        except (ValueError, TypeError) as exc:
            _audit("failed", request_id=request_id, capability=capability, classification=decision["classification"], error_type=type(exc).__name__)
            return {"request_id": request_id, "status": "error", "decision": decision, "error": str(exc)[:200]}
        _audit("shell_gate_set", request_id=request_id, capability=capability, classification=decision["classification"], host=host, enabled=bool(result.get("enabled")), expires_at_unix=result.get("expires_at_unix"), generation=result.get("generation", 0))
        return {"request_id": request_id, "status": "completed", "decision": decision, "result": result}

    shell_host = "edge1" if capability == "edge1.shell.exec" else "business159" if capability == "business159.shell.exec" else None
    if shell_host is not None:
        gate = shell_gate_status(shell_host)
        if not gate.get("enabled"):
            _audit("denied", request_id=request_id, capability=capability, classification=decision["classification"], reason="shell_gate_disabled", host=shell_host)
            denied = dict(decision); denied["allowed"] = False; denied["reason"] = "shell_gate_disabled"
            return {"request_id": request_id, "status": "denied", "decision": denied, "gate": gate}

    started = time.monotonic()
    try:
        if capability in EDGE1_READ_TOOLS:
            result = _mcp(EDGE1_OPERATOR_URL, EDGE1_READ_TOOLS[capability], {})
        elif capability == "edge1.service.repair":
            service = str(arguments.get("service", ""))
            action = str(arguments.get("action", "status"))
            if service not in SAFE_SERVICES or action not in {"status", "restart", "reload"}:
                raise ValueError("service repair request is outside the allowlist")
            result = _mcp(EDGE1_SHELL_URL, "edge1_agent_service", {"service": service, "action": action, "timeout_ms": 120000})
        elif capability == "edge1.shell.exec":
            command = str(arguments.get("command", ""))
            if not command or len(command) > 65536:
                raise ValueError("invalid Edge1 command")
            result = _mcp(EDGE1_SHELL_URL, "edge1_agent_exec", {"command": command, "timeout_ms": min(900000, max(1000, int(arguments.get("timeout_ms", 120000)))), "max_output_bytes": 131072, "redact_output": True})
        elif capability in BUSINESS159_READ_COMMANDS:
            result = _business159(BUSINESS159_READ_COMMANDS[capability])
        elif capability == "business159.deploy":
            expected = str(arguments.get("expected_commit", ""))
            dry_run = bool(arguments.get("dry_run", True))
            if not re.fullmatch(r"[a-f0-9]{40}", expected):
                raise ValueError("exact expected commit is required")
            cmd = f"cd ~/apps/ww-cx-website; test \"$(git rev-parse HEAD)\" = {expected}; ~/apps/ww-cx-website/scripts/deploy-business159.sh" + (" --dry-run" if dry_run else "")
            result = _business159(cmd, timeout=180)
        elif capability == "business159.shell.exec":
            command = str(arguments.get("command", ""))
            if not command:
                raise ValueError("invalid Business159 command")
            result = _business159(command, timeout=min(300, max(1, int(arguments.get("timeout_seconds", 60)))))
        else:
            raise ValueError("capability has no broker implementation")
        duration_ms = max(0, int((time.monotonic() - started) * 1000))
        _audit("completed", request_id=request_id, capability=capability, classification=decision["classification"], duration_ms=duration_ms, ok=bool(result.get("ok", True)))
        return {"request_id": request_id, "status": "completed", "decision": decision, "result": result}
    except Exception as exc:
        duration_ms = max(0, int((time.monotonic() - started) * 1000))
        _audit("failed", request_id=request_id, capability=capability, classification=decision["classification"], duration_ms=duration_ms, error_type=type(exc).__name__)
        return {"request_id": request_id, "status": "error", "decision": decision, "error": str(exc)[:200]}


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "wwcx-ava-operator-broker/1"
    token: str = ""

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._json(200, {"status": "ok", "service": "wwcx-ava-operator-broker", "policy": "ava-operator-parity", "secrets_exposed": False})
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/invoke":
            self._json(404, {"error": "not_found"}); return
        supplied = self.headers.get("Authorization", "")
        if not supplied.startswith("Bearer ") or not hmac.compare_digest(hashlib.sha256(supplied[7:].encode()).digest(), hashlib.sha256(self.token.encode()).digest()):
            self._json(401, {"error": "unauthorized"}); return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._json(413, {"error": "invalid_body_size"}); return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._json(400, {"error": "invalid_json"}); return
        if not isinstance(payload, dict) or set(payload) - {"capability", "arguments", "confirmed"}:
            self._json(400, {"error": "invalid_request"}); return
        capability = payload.get("capability")
        arguments = payload.get("arguments", {})
        confirmed = payload.get("confirmed", False)
        if not isinstance(capability, str) or not isinstance(arguments, dict) or not isinstance(confirmed, bool):
            self._json(400, {"error": "invalid_request"}); return
        result = invoke(capability, arguments, confirmed)
        self._json(200 if result["status"] in {"completed", "denied"} else 502, result)


def serve(host: str, port: int, token_path: Path) -> None:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise RuntimeError("Ava operator broker must remain loopback-only")
    Handler.token = _private_token(token_path)
    server = http.server.ThreadingHTTPServer((host, port), Handler)
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--token", type=Path, default=DEFAULT_TOKEN)
    args = parser.parse_args()
    serve(args.host, args.port, args.token)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
