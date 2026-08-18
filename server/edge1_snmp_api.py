#!/usr/bin/env python3
"""Loopback-only authenticated HTTP API for the Edge1 SNMP platform."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from edge1_snmp_platform import (
    add_device, audit, connect_db, evidence_query, get_device, health, list_devices,
    normalize_trap, propose_action, utcnow,
)
from edge1_snmp_services import AlertEngine, DiscoveryService, MIBService, ensure_extended_schema, get_topology, search_all

SECRET_FILE = Path(os.environ.get("EDGE1_SNMP_API_SECRET_FILE", "/etc/edge1-snmp/api.secret"))
MAX_BODY = 65536
MAX_CLOCK_SKEW = 300
NONCES: dict[str, int] = {}


def read_secret() -> bytes:
    value = SECRET_FILE.read_bytes().strip()
    if len(value) < 32:
        raise ValueError("API secret must contain at least 32 bytes")
    return value


def authenticate(headers, method: str, path: str, body: bytes) -> tuple[bool, str, str]:
    actor = headers.get("X-WWCX-Actor", "").strip()
    nonce = headers.get("X-WWCX-Nonce", "").strip()
    timestamp_text = headers.get("X-WWCX-Timestamp", "").strip()
    supplied = headers.get("X-WWCX-Signature", "").strip().lower()
    if not actor or not nonce or not timestamp_text or not supplied:
        return False, "missing authentication headers", ""
    try:
        ts = int(timestamp_text)
    except ValueError:
        return False, "invalid timestamp", actor
    now = int(time.time())
    if abs(now - ts) > MAX_CLOCK_SKEW:
        return False, "timestamp outside allowed window", actor
    cutoff = now - MAX_CLOCK_SKEW
    for key, seen in list(NONCES.items()):
        if seen < cutoff:
            NONCES.pop(key, None)
    if nonce in NONCES:
        return False, "replayed nonce", actor
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((method, path, timestamp_text, nonce, actor, body_hash)).encode()
    expected = hmac.new(read_secret(), canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        return False, "invalid signature", actor
    NONCES[nonce] = ts
    return True, body_hash, actor


class Handler(BaseHTTPRequestHandler):
    server_version = "Edge1SNMPAPI/1"

    def log_message(self, fmt, *args):
        return

    def send_json(self, status: int, payload):
        data = json.dumps(payload, sort_keys=True, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def read_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid content length") from exc
        if length < 0 or length > MAX_BODY:
            raise ValueError("request body too large")
        return self.rfile.read(length)

    def require_auth(self, body: bytes = b"") -> tuple[bool, str]:
        ok, detail, actor = authenticate(self.headers, self.command, self.path, body)
        if not ok:
            self.send_json(401, {"error": detail})
            return False, ""
        return True, actor

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/snmp/health":
            try:
                with connect_db() as conn:
                    self.send_json(200, health(conn))
            except Exception as exc:
                self.send_json(503, {"status": "error", "detail": str(exc)[:500]})
            return
        ok, actor = self.require_auth()
        if not ok:
            return
        try:
            with connect_db() as conn:
                ensure_extended_schema(conn)
                if parsed.path == "/api/snmp/devices":
                    self.send_json(200, {"devices": list_devices(conn)}); return
                if parsed.path.endswith("/interfaces") and parsed.path.startswith("/api/snmp/devices/"):
                    device_id = parsed.path.split("/")[4]
                    rows = [dict(r) for r in conn.execute("SELECT * FROM interfaces WHERE device_id=? ORDER BY if_index", (device_id,))]
                    self.send_json(200, {"interfaces": rows}); return
                if parsed.path.endswith("/metrics") and parsed.path.startswith("/api/snmp/devices/"):
                    device_id = parsed.path.split("/")[4]
                    limit = min(5000, max(1, int(parse_qs(parsed.query).get("limit", [500])[0])))
                    rows = [dict(r) for r in conn.execute("SELECT * FROM metrics WHERE device_id=? ORDER BY ts DESC LIMIT ?", (device_id, limit))]
                    self.send_json(200, {"metrics": rows}); return
                if parsed.path.startswith("/api/snmp/devices/"):
                    device_id = parsed.path.rsplit("/", 1)[-1]
                    self.send_json(200, get_device(conn, device_id)); return
                if parsed.path == "/api/snmp/topology":
                    self.send_json(200, get_topology(conn)); return
                if parsed.path == "/api/snmp/search":
                    q = parse_qs(parsed.query).get("q", [""])[0]
                    self.send_json(200, search_all(conn, q)); return
                if parsed.path == "/api/snmp/mibs":
                    rows = [dict(r) for r in conn.execute("SELECT * FROM mib_imports ORDER BY imported_at DESC LIMIT 500")]
                    self.send_json(200, {"imports": rows}); return
                if parsed.path == "/api/snmp/events":
                    limit = min(500, max(1, int(parse_qs(parsed.query).get("limit", [100])[0])))
                    rows = [dict(r) for r in conn.execute("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,))]
                    self.send_json(200, {"events": rows}); return
                if parsed.path == "/api/snmp/alerts":
                    rows = [dict(r) for r in conn.execute("SELECT * FROM alerts ORDER BY updated_at DESC LIMIT 500")]
                    self.send_json(200, {"alerts": rows}); return
                if parsed.path == "/api/snmp/audit":
                    rows = [dict(r) for r in conn.execute("SELECT * FROM audit ORDER BY ts DESC LIMIT 500")]
                    self.send_json(200, {"audit": rows}); return
                if parsed.path == "/api/snmp/oids":
                    q = parse_qs(parsed.query).get("q", [""])[0][:200]
                    if q:
                        like = f"%{q}%"
                        rows = [dict(r) for r in conn.execute("SELECT * FROM mib_objects WHERE oid LIKE ? OR name LIKE ? OR module LIKE ? LIMIT 100", (like, like, like))]
                    else:
                        rows = [dict(r) for r in conn.execute("SELECT * FROM mib_objects ORDER BY oid LIMIT 100")]
                    self.send_json(200, {"oids": rows}); return
        except KeyError:
            self.send_json(404, {"error": "not found"}); return
        except Exception as exc:
            self.send_json(400, {"error": str(exc)[:1000]}); return
        self.send_json(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = self.read_body()
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)}); return
        ok, actor = self.require_auth(body)
        if not ok:
            return
        try:
            payload = json.loads(body or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            with connect_db() as conn:
                ensure_extended_schema(conn)
                if self.path == "/api/snmp/devices":
                    self.send_json(201, add_device(conn, payload, actor=actor)); return
                if self.path == "/api/snmp/discovery":
                    cidr = str(payload.get("cidr") or "")
                    profile = str(payload.get("credential_reference") or "")
                    if not cidr or not profile:
                        raise ValueError("cidr and credential_reference are required")
                    result = __import__("asyncio").run(DiscoveryService().scan(
                        cidr, profile, dry_run=bool(payload.get("dry_run", True)),
                        concurrency=int(payload.get("concurrency", 16))))
                    audit(conn, actor=actor, source="api", action="discovery.scan", target=cidr,
                          reason="bounded SNMP discovery", result="preview" if result.get("dry_run") else "succeeded")
                    self.send_json(200, result); return
                if self.path == "/api/snmp/mibs/import":
                    module = str(payload.get("module") or "")
                    result = MIBService(conn).import_net_snmp_module(module, mib_dirs=payload.get("mib_dirs"))
                    audit(conn, actor=actor, source="api", action="mib.import", target=module,
                          reason="operator MIB import", result=result["status"])
                    self.send_json(201, result); return
                if self.path == "/api/snmp/alerts/evaluate":
                    result = AlertEngine(conn).evaluate()
                    audit(conn, actor=actor, source="deterministic", action="alerts.evaluate", target=None,
                          reason="scheduled alert evaluation", result="succeeded")
                    self.send_json(200, result); return
                if self.path == "/api/snmp/traps":
                    result = normalize_trap(conn, payload)
                    audit(conn, actor=actor, source="trap-ingest", action="trap.ingest", target=result["event_id"],
                          reason="SNMP trap/inform normalization", result="duplicate" if result.get("duplicate") else "succeeded")
                    self.send_json(200, result); return
                if self.path == "/api/snmp/ai/query":
                    question = str(payload.get("question") or "")[:4000]
                    if not question:
                        raise ValueError("question is required")
                    response = evidence_query(conn, question)
                    audit(conn, actor=actor, source="ai", action="ai.query", target=None, reason=question[:500],
                          result="succeeded", ai_involvement="analysis")
                    self.send_json(200, response); return
                if self.path == "/api/snmp/actions":
                    result = propose_action(conn, actor=actor, action=str(payload.get("action") or ""),
                                            target=payload.get("target"), reason=str(payload.get("reason") or "")[:1000],
                                            ai_involvement=bool(payload.get("ai_involvement", False)),
                                            validation=payload.get("validation"), rollback=payload.get("rollback"))
                    self.send_json(201, result); return
        except json.JSONDecodeError:
            self.send_json(400, {"error": "invalid JSON"}); return
        except Exception as exc:
            self.send_json(400, {"error": str(exc)[:1000]}); return
        self.send_json(404, {"error": "not found"})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("EDGE1_SNMP_API_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("EDGE1_SNMP_API_PORT", "8112")))
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "::1"}:
        raise SystemExit("refusing non-loopback API bind")
    read_secret()
    connect_db().close()
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
