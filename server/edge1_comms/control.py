"""Loopback-only read-only HTTP control surface for Edge1 Comms Relay."""

from __future__ import annotations

import json
import urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from .config import RelayConfig, sanitized_config
from .storage import CommsStore


class ControlHandler(SimpleHTTPRequestHandler):
    server: "ControlServer"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        server = args[2]
        super().__init__(*args, directory=str(server.web_root), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; object-src 'none'")
        self.send_header("Permissions-Policy", "camera=(), geolocation=(), microphone=()")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        super().end_headers()

    def send_json(self, status: HTTPStatus, payload: dict[str, Any] | list[Any]) -> None:
        body = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/api/comms/status":
            self.send_json(
                HTTPStatus.OK,
                {
                    "service": "edge1-comms-relay",
                    "version": "0.1.0",
                    "config": sanitized_config(self.server.cfg),
                    "storage": self.server.store.stats(),
                    "irc": self.server.irc_summary(),
                    "federation": {"irc": "disabled", "nntp": "disabled"},
                },
            )
            return
        if parsed.path == "/api/comms/news/groups":
            self.send_json(HTTPStatus.OK, self.server.store.list_groups())
            return
        if parsed.path == "/api/comms/audit":
            try:
                limit = max(1, min(int(params.get("limit", ["100"])[0]), 500))
            except ValueError:
                limit = 100
            self.send_json(HTTPStatus.OK, self.server.store.recent_audit(limit))
            return
        if parsed.path.startswith("/api/"):
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        super().do_GET()

    def do_POST(self) -> None:
        self.send_json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "read_only_control_api"})

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST


class ControlServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        cfg: RelayConfig,
        store: CommsStore,
        *,
        web_root: str | Path,
        irc_summary: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.cfg = cfg
        self.store = store
        self.web_root = Path(web_root)
        self._irc_summary = irc_summary
        super().__init__(address, ControlHandler)

    def irc_summary(self) -> dict[str, Any]:
        if self._irc_summary is None:
            return {"connected_users": None, "channels": [], "mode": "standalone-control"}
        payload = self._irc_summary()
        payload["mode"] = "live"
        return payload
