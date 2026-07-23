#!/usr/bin/env python3
"""Authenticated operator API for the Telegraph federation reference stack.

The API intentionally defaults to read-only operation. Mutating endpoints are
limited to alert acknowledgement and message cancellation, both of which are
audited. Trust, key, routing, and production transport changes are not exposed.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from reference.telegraph_control_plane import TelegraphControlPlane
from reference.telegraph_observability import TelegraphObservability
from reference.telegraph_store_forward import TelegraphStoreForwardQueue


READ_SCOPES = {
    "telegraph.dashboard.read",
    "telegraph.queue.read",
    "telegraph.federation.read",
    "telegraph.routing.read",
    "telegraph.events.read",
    "telegraph.alerts.read",
    "telegraph.diagnostics.read",
}
WRITE_SCOPES = {"telegraph.alerts.acknowledge", "telegraph.queue.cancel"}
ALL_SCOPES = READ_SCOPES | WRITE_SCOPES


@dataclass(frozen=True)
class Principal:
    subject: str
    scopes: frozenset[str]

    def permits(self, scope: str) -> bool:
        return scope in self.scopes


class TokenAuthenticator:
    """Constant-time bearer-token authentication using stored SHA-256 digests."""

    def __init__(self, tokens: dict[str, tuple[str, set[str]]]) -> None:
        self._tokens = {
            hashlib.sha256(token.encode("utf-8")).digest(): Principal(subject, frozenset(scopes))
            for token, (subject, scopes) in tokens.items()
            if token
        }

    @classmethod
    def from_environment(cls, variable: str = "TELEGRAPH_ADMIN_TOKENS_JSON") -> "TokenAuthenticator":
        raw = os.environ.get(variable, "")
        if not raw:
            return cls({})
        document = json.loads(raw)
        if not isinstance(document, list):
            raise ValueError(f"{variable} must contain a JSON array")
        tokens: dict[str, tuple[str, set[str]]] = {}
        for item in document:
            if not isinstance(item, dict):
                raise ValueError("token entries must be objects")
            token = item.get("token")
            subject = item.get("subject")
            scopes = item.get("scopes", [])
            if not isinstance(token, str) or not isinstance(subject, str) or not isinstance(scopes, list):
                raise ValueError("invalid token entry")
            normalized = {str(scope) for scope in scopes}
            unknown = normalized - ALL_SCOPES
            if unknown:
                raise ValueError(f"unknown scopes: {sorted(unknown)}")
            tokens[token] = (subject, normalized)
        return cls(tokens)

    def authenticate(self, authorization: str | None) -> Principal | None:
        if not authorization or not authorization.startswith("Bearer "):
            return None
        token = authorization[7:].strip()
        if not token:
            return None
        candidate = hashlib.sha256(token.encode("utf-8")).digest()
        for digest, principal in self._tokens.items():
            if hmac.compare_digest(candidate, digest):
                return principal
        return None


@dataclass
class TelegraphAdminState:
    office_id: str
    queue: TelegraphStoreForwardQueue
    control_plane: TelegraphControlPlane
    observability: TelegraphObservability
    authenticator: TokenAuthenticator
    queue_capacity_messages: int | None = None
    route_decisions: list[dict[str, Any]] = field(default_factory=list)
    lock: threading.RLock = field(default_factory=threading.RLock)
    started_at: float = field(default_factory=time.time)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            queue_summary = self.observability.queue_summary(self.queue.connection)
            control_snapshot = self.control_plane.snapshot()
            peer_summary = self.observability.peer_summary(control_snapshot)
            route_summary = self.observability.route_summary(self.route_decisions)
            self.observability.evaluate_alerts(
                queue_summary,
                peer_summary,
                queue_capacity_messages=self.queue_capacity_messages,
            )
            return self.observability.dashboard_snapshot(queue_summary, peer_summary, route_summary)

    def diagnostic_bundle(self) -> dict[str, Any]:
        dashboard = self.snapshot()
        configuration = {
            "office_id": self.office_id,
            "queue_capacity_messages": self.queue_capacity_messages,
            "control_plane_policy": vars(self.control_plane.policy),
            "observability_thresholds": vars(self.observability.thresholds),
        }
        return self.observability.diagnostic_bundle(dashboard, configuration)

    def audit(self, principal: Principal, action: str, detail: dict[str, Any]) -> None:
        self.observability.record_event(
            source="admin_api",
            event_type=action,
            summary=f"Operator {principal.subject} performed {action}",
            severity="info",
            office_id=self.office_id,
            message_id=detail.get("message_id"),
            detail={"operator": principal.subject, **detail},
        )


class TelegraphAdminHandler(BaseHTTPRequestHandler):
    server_version = "WWCXTelegraphAdmin/0.1"

    @property
    def state(self) -> TelegraphAdminState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _json(self, status: HTTPStatus, payload: Any) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _principal(self, scope: str) -> Principal | None:
        principal = self.state.authenticator.authenticate(self.headers.get("Authorization"))
        if principal is None:
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication_required"})
            return None
        if not principal.permits(scope):
            self._json(HTTPStatus.FORBIDDEN, {"error": "insufficient_scope", "required_scope": scope})
            return None
        return principal

    def _read_json(self, maximum: int = 64 * 1024) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length <= 0 or length > maximum:
            return None
        try:
            value = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if path == "/healthz":
            self._json(HTTPStatus.OK, {
                "status": "ok",
                "office_id": self.state.office_id,
                "uptime_seconds": int(time.time() - self.state.started_at),
            })
            return
        if path == "/v1/dashboard":
            if self._principal("telegraph.dashboard.read"):
                self._json(HTTPStatus.OK, self.state.snapshot())
            return
        if path == "/v1/queue":
            if self._principal("telegraph.queue.read"):
                self._json(HTTPStatus.OK, self.state.observability.queue_summary(self.state.queue.connection))
            return
        if path.startswith("/v1/queue/messages/"):
            if not self._principal("telegraph.queue.read"):
                return
            message_id = path.split("/")[-1]
            try:
                payload = {
                    "status": self.state.queue.status(message_id),
                    "events": self.state.queue.events(message_id),
                }
            except KeyError:
                self._json(HTTPStatus.NOT_FOUND, {"error": "message_not_found"})
            else:
                self._json(HTTPStatus.OK, payload)
            return
        if path == "/v1/federation":
            if self._principal("telegraph.federation.read"):
                snapshot = self.state.control_plane.snapshot()
                self._json(HTTPStatus.OK, {
                    "snapshot": snapshot,
                    "summary": self.state.observability.peer_summary(snapshot),
                })
            return
        if path == "/v1/routes":
            if self._principal("telegraph.routing.read"):
                self._json(HTTPStatus.OK, {
                    "summary": self.state.observability.route_summary(self.state.route_decisions),
                    "recent_decisions": self.state.route_decisions[-100:],
                })
            return
        if path == "/v1/events":
            if not self._principal("telegraph.events.read"):
                return
            try:
                limit = int(query.get("limit", ["100"])[0])
                severity = query.get("minimum_severity", ["info"])[0]
                events = self.state.observability.timeline(
                    limit=limit,
                    minimum_severity=severity,
                    office_id=query.get("office_id", [None])[0],
                    message_id=query.get("message_id", [None])[0],
                )
            except (TypeError, ValueError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "detail": str(exc)})
            else:
                self._json(HTTPStatus.OK, {"events": events})
            return
        if path == "/v1/alerts":
            if not self._principal("telegraph.alerts.read"):
                return
            status = query.get("status", [None])[0]
            try:
                alerts = self.state.observability.alerts(status=status)
            except ValueError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_query", "detail": str(exc)})
            else:
                self._json(HTTPStatus.OK, {"alerts": alerts})
            return
        if path == "/v1/diagnostics":
            if self._principal("telegraph.diagnostics.read"):
                self._json(HTTPStatus.OK, self.state.diagnostic_bundle())
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path.startswith("/v1/alerts/") and path.endswith("/acknowledge"):
            principal = self._principal("telegraph.alerts.acknowledge")
            if principal is None:
                return
            alert_key = path[len("/v1/alerts/"):-len("/acknowledge")].strip("/")
            if not alert_key:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "alert_key_required"})
                return
            try:
                self.state.observability.acknowledge_alert(alert_key, principal.subject)
            except KeyError:
                self._json(HTTPStatus.NOT_FOUND, {"error": "active_alert_not_found"})
                return
            self.state.audit(principal, "alert_acknowledged", {"alert_key": alert_key})
            self._json(HTTPStatus.OK, {"status": "acknowledged", "alert_key": alert_key})
            return
        if path.startswith("/v1/queue/messages/") and path.endswith("/cancel"):
            principal = self._principal("telegraph.queue.cancel")
            if principal is None:
                return
            message_id = path[len("/v1/queue/messages/"):-len("/cancel")].strip("/")
            document = self._read_json()
            if document is None or not isinstance(document.get("reason"), str) or not document["reason"].strip():
                self._json(HTTPStatus.BAD_REQUEST, {"error": "cancellation_reason_required"})
                return
            try:
                cancelled = self.state.queue.cancel(message_id, document["reason"].strip())
            except KeyError:
                self._json(HTTPStatus.NOT_FOUND, {"error": "message_not_found"})
                return
            if not cancelled:
                self._json(HTTPStatus.CONFLICT, {"error": "message_not_cancellable"})
                return
            self.state.audit(principal, "message_cancelled", {
                "message_id": message_id,
                "reason": document["reason"].strip(),
            })
            self._json(HTTPStatus.OK, {"status": "cancelled", "message_id": message_id})
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})


def serve(
    host: str,
    port: int,
    office_id: str,
    queue_database: Path,
    observability_database: Path,
    queue_capacity_messages: int | None = None,
) -> None:
    authenticator = TokenAuthenticator.from_environment()
    queue = TelegraphStoreForwardQueue(queue_database, office_id)
    observability = TelegraphObservability(observability_database, office_id)
    control_plane = TelegraphControlPlane(office_id)
    state = TelegraphAdminState(
        office_id=office_id,
        queue=queue,
        control_plane=control_plane,
        observability=observability,
        authenticator=authenticator,
        queue_capacity_messages=queue_capacity_messages,
    )
    server = ThreadingHTTPServer((host, port), TelegraphAdminHandler)
    server.state = state  # type: ignore[attr-defined]
    try:
        server.serve_forever()
    finally:
        server.server_close()
        observability.close()
        queue.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8098)
    parser.add_argument("--office-id", required=True)
    parser.add_argument("--queue-database", type=Path, required=True)
    parser.add_argument("--observability-database", type=Path, required=True)
    parser.add_argument("--queue-capacity-messages", type=int)
    arguments = parser.parse_args()
    serve(
        arguments.host,
        arguments.port,
        arguments.office_id,
        arguments.queue_database,
        arguments.observability_database,
        arguments.queue_capacity_messages,
    )


if __name__ == "__main__":
    main()
