#!/usr/bin/env python3
"""G2 single-user local-only API: authenticated candidate previews, NEVER apply.

Listen only on loopback; connect from Windows through an SSH port forward.
The token is read from a private local file, never logged or persisted in JS.
Static UI is local-only; all candidate and observation API routes require token.
No endpoint changes DNS, routing, services, nftables or running configuration.
"""
from __future__ import annotations
import argparse
import hmac
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from edge1_candidate_store import CandidateStore, CandidateError, ConflictError

MAX_BODY = 4096
MAX_OBSERVATION = 256 * 1024


def read_observation(path: Path) -> dict:
    """Freshness-labeled, minimal whitelisted observation; NEVER a config source."""
    from datetime import datetime, timezone
    unavailable = {"available": False, "fresh": False, "reason": "observation unavailable"}
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_OBSERVATION:
            return unavailable
        document = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(document, dict) or document.get("schema_version") != "wwcx.core-observation.v1"
                or document.get("read_only") is not True):
            return unavailable
        generated = datetime.fromisoformat(document["generated_at"].replace("Z", "+00:00"))
        if generated.tzinfo is None:
            return unavailable
        age = (datetime.now(timezone.utc) - generated).total_seconds()
        fresh = -60 <= age <= 300
        services = document.get("services", {})
        if not isinstance(services, dict):
            services = {}
        active = sum(1 for v in services.values() if isinstance(v, dict) and v.get("state") == "active")
        return {
            "available": True, "fresh": fresh,
            "generated_at": generated.isoformat(),
            "age_seconds": int(age),
            "service_count": min(len(services), 10000),
            "active_service_count": active,
            "reason": "current" if fresh else "stale; never treat as healthy",
            "source": "existing read-only core-status.json; not running configuration",
        }
    except (OSError, ValueError, TypeError, KeyError):
        return unavailable


class LocalHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address, ui: Path, store: CandidateStore, token: str, observation: Path):
        if address[0] != "127.0.0.1":
            raise ValueError("G2 only accepts 127.0.0.1")
        self.ui = ui
        self.store = store
        self.token = token
        self.observation = observation
        super().__init__(address, CandidateHandler)


class CandidateHandler(BaseHTTPRequestHandler):
    server: LocalHTTPServer

    def log_message(self, format, *args):
        # Never log request headers or authorization secrets.
        return

    def reply(self, status: int, payload: dict):
        content = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("ascii")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _authorized(self) -> bool:
        if self.headers.get("Host") not in (f"127.0.0.1:{self.server.server_port}",):
            self.reply(403, {"error": "unexpected Host; use the SSH loopback tunnel"})
            return False
        supplied = self.headers.get("X-Edge1-Token", "")
        if not supplied or not hmac.compare_digest(supplied, self.server.token):
            self.reply(401, {"error": "authentication required"})
            return False
        return True

    def _route(self) -> str:
        return urlsplit(self.path).path

    def do_GET(self):
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            self.reply(403, {"error": "unexpected Host"})
            return
        if self._route() == "/":
            payload = self.server.ui.read_bytes()
            self.send_response(200)
            for key, value in {
                "Content-Type": "text/html; charset=utf-8",
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
                "Content-Length": str(len(payload)),
            }.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(payload)
            return
        if not self._authorized():
            return
        if self._route() == "/api/state":
            self.reply(200, self.server.store.read())
        elif self._route() == "/api/audit":
            self.reply(200, {"events": self.server.store.audit()})
        elif self._route() == "/api/observation":
            self.reply(200, read_observation(self.server.observation))
        else:
            self.reply(404, {"error": "unknown API route"})

    def do_POST(self):
        if not self._authorized():
            return
        if self.headers.get("Origin") != f"http://127.0.0.1:{self.server.server_port}":
            self.reply(403, {"error": "exact local Origin required"})
            return
        route = self._route()
        if route not in ("/api/propose", "/api/discard"):
            self.reply(404, {"error": "unknown API route"})
            return
        if self.headers.get("Content-Type") != "application/json":
            self.reply(415, {"error": "application/json required"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                self.reply(413, {"error": "request size invalid"})
                return
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise CandidateError("JSON object expected")
            if route == "/api/propose":
                if set(data) != {"expected_candidate_revision", "section", "field", "value"}:
                    raise CandidateError("Unexpected proposal fields")
                result = self.server.store.propose(data["section"], data["field"], data["value"],
                    expected_candidate_revision=data["expected_candidate_revision"])
            else:
                if set(data) != {"expected_candidate_revision"}:
                    raise CandidateError("Unexpected discard fields")
                result = self.server.store.discard(expected_candidate_revision=data["expected_candidate_revision"])
            self.reply(200, result)
        except ConflictError as exc:
            self.reply(409, {"error": str(exc)})
        except (CandidateError, ValueError, KeyError, TypeError) as exc:
            self.reply(422, {"error": str(exc)})

    def do_OPTIONS(self):
        self.reply(405, {"error": "cross-origin requests unsupported"})

    def do_PUT(self):
        self.reply(405, {"error": "unsupported method"})

    def do_DELETE(self):
        self.reply(405, {"error": "unsupported method"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--observation", type=Path, default=Path("/var/www/edge1-status/core-status.json"))
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    os.umask(0o077)
    if not 1024 <= args.port <= 65535:
        parser.error("port out of range")
    if args.token_file.is_symlink() or (args.token_file.stat().st_mode & 0o077):
        parser.error("private token file must not be a symlink or group/world readable")
    token = args.token_file.read_text(encoding="ascii").strip()
    if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        parser.error("expected 256-bit lowercase hexadecimal token")
    if not args.ui.is_file() or args.ui.is_symlink():
        parser.error("invalid local static UI")
    store = CandidateStore(args.database)
    server = LocalHTTPServer(("127.0.0.1", args.port), args.ui, store, token, args.observation)
    print(f"G2 local-only API on 127.0.0.1:{args.port}; SSH forwarding required", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
