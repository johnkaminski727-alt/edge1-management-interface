#!/usr/bin/env python3
"""Loopback-only read API and static workspace for WW.CX Communications."""

from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
WEB_ROOT = REPO_ROOT / "src" / "web" / "communications"
SHELL_ROOT = REPO_ROOT / "src" / "web" / "operator-shell"
NAVIGATION_PATH = REPO_ROOT / "config" / "edge1_operator" / "navigation_registry.json"
READINESS_PATH = REPO_ROOT / "config" / "communications" / "readiness-matrix-v1.json"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import unified_communications as core  # noqa: E402


class CommunicationsWorkspaceError(RuntimeError):
    pass


class SnapshotStore:
    """Read canonical metadata events from an operator-supplied JSONL snapshot."""

    def __init__(self, snapshot_path: Path | None = None) -> None:
        self.snapshot_path = snapshot_path.resolve() if snapshot_path else None

    def events(self) -> list[dict[str, Any]]:
        if self.snapshot_path is None:
            return []
        if not self.snapshot_path.is_file():
            raise CommunicationsWorkspaceError("communications event snapshot is unavailable")
        if self.snapshot_path.stat().st_size > 32 * 1024 * 1024:
            raise CommunicationsWorkspaceError("communications event snapshot exceeds 32 MiB")
        events: list[dict[str, Any]] = []
        for line_number, raw_line in enumerate(self.snapshot_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw_line.strip():
                continue
            try:
                value = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise CommunicationsWorkspaceError(f"invalid snapshot JSON on line {line_number}") from exc
            try:
                events.append(core.validate_event(value))
            except core.CommunicationsContractError as exc:
                raise CommunicationsWorkspaceError(f"invalid canonical event on line {line_number}: {exc}") from exc
        return core.sort_events(events)

    def query(self, *, text: str = "", channel: str = "all", conversation_id: str = "", state: str = "", limit: int = 100) -> list[dict[str, Any]]:
        events = self.events()
        if channel and channel != "all":
            if channel not in core.CHANNELS:
                raise CommunicationsWorkspaceError("unsupported channel filter")
            events = [item for item in events if item["channel"] == channel]
        if conversation_id:
            events = [item for item in events if item.get("conversation_id") == conversation_id]
        if state:
            if state not in core.STATES:
                raise CommunicationsWorkspaceError("unsupported state filter")
            events = [item for item in events if item["status"] == state]
        if text.strip():
            events = core.search_events(events, text)
        bounded_limit = min(max(int(limit), 1), 500)
        return events[-bounded_limit:]


class CommunicationsApplication:
    def __init__(self, snapshot_path: Path | None = None) -> None:
        self.store = SnapshotStore(snapshot_path)

    def readiness(self) -> dict[str, Any]:
        return json.loads(READINESS_PATH.read_text(encoding="utf-8"))

    def query(self, query: dict[str, list[str]]) -> dict[str, Any]:
        raw_limit = query.get("limit", ["100"])[0]
        try:
            limit = int(raw_limit)
        except ValueError as exc:
            raise CommunicationsWorkspaceError("limit must be an integer") from exc
        events = self.store.query(
            text=query.get("q", [""])[0],
            channel=query.get("channel", ["all"])[0],
            conversation_id=query.get("conversation_id", [""])[0],
            state=query.get("state", [""])[0],
            limit=limit,
        )
        return {"contract": "wwcx.communications-workspace-read.v1", "events": events, "count": len(events), "content_is_untrusted": True, "mutation_authorized": False}

    def event(self, event_id: str) -> dict[str, Any] | None:
        for item in self.store.events():
            if item["communications_event_id"] == event_id:
                return item
        return None


class CommunicationsHandler(BaseHTTPRequestHandler):
    server_version = "WWCXCommunicationsWorkspace/1.0"

    @property
    def application(self) -> CommunicationsApplication:
        return self.server.application  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))

    def _headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self._headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        self._send(status, json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"), "application/json; charset=utf-8")

    def _asset_from(self, root: Path, name: str, content_type: str) -> None:
        root = root.resolve()
        path = (root / name).resolve()
        if root not in path.parents or not path.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "asset_not_found"})
            return
        self._send(HTTPStatus.OK, path.read_bytes(), content_type)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path in {"/communications", "/communications/"}:
                self._asset_from(WEB_ROOT, "index.html", "text/html; charset=utf-8")
                return
            if parsed.path == "/communications/app.js":
                self._asset_from(WEB_ROOT, "app.js", "text/javascript; charset=utf-8")
                return
            if parsed.path == "/communications/styles.css":
                self._asset_from(WEB_ROOT, "styles.css", "text/css; charset=utf-8")
                return
            if parsed.path == "/communications/operator-shell/shell.js":
                self._asset_from(SHELL_ROOT, "shell.js", "text/javascript; charset=utf-8")
                return
            if parsed.path == "/communications/operator-shell/shell.css":
                self._asset_from(SHELL_ROOT, "shell.css", "text/css; charset=utf-8")
                return
            if parsed.path == "/communications/operator-shell/navigation.json":
                self._send(HTTPStatus.OK, NAVIGATION_PATH.read_bytes(), "application/json; charset=utf-8")
                return
            if parsed.path == "/communications/healthz":
                self._json(HTTPStatus.OK, {"status": "ok", "service": "wwcx-communications-workspace", "mode": "read_only"})
                return
            if parsed.path == "/communications/api/v1/readiness":
                self._json(HTTPStatus.OK, self.application.readiness())
                return
            if parsed.path == "/communications/api/v1/events":
                self._json(HTTPStatus.OK, self.application.query(parse_qs(parsed.query)))
                return
            prefix = "/communications/api/v1/events/"
            if parsed.path.startswith(prefix):
                event_id = parsed.path[len(prefix):]
                if not event_id or "/" in event_id:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_event_id"})
                    return
                item = self.application.event(event_id)
                if item is None:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "event_not_found"})
                    return
                self._json(HTTPStatus.OK, {"contract": "wwcx.communications-workspace-read.v1", "event": item, "mutation_authorized": False})
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except CommunicationsWorkspaceError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request", "message": str(exc)})
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "workspace_unavailable", "message": str(exc)})

    def do_POST(self) -> None:
        self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "read_only_workspace", "mutation_authorized": False})

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST


class CommunicationsServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], application: CommunicationsApplication) -> None:
        super().__init__(address, CommunicationsHandler)
        self.application = application


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8095)
    parser.add_argument("--event-snapshot", type=Path, default=None)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("Refusing non-loopback bind; use an authenticated reverse proxy")
    server = CommunicationsServer((args.host, args.port), CommunicationsApplication(args.event_snapshot))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
