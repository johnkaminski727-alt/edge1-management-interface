#!/usr/bin/env python3
"""Loopback-only read surface for the WW.CX Number Portability Center."""
from __future__ import annotations

import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8117
MAX_LIMIT = 100


class PortReadError(RuntimeError):
    pass


class PortReadModel:
    def __init__(self, database: str | Path) -> None:
        self.database = Path(database)

    def _connect(self) -> sqlite3.Connection:
        if not self.database.is_file():
            raise PortReadError("portability database is unavailable")
        conn = sqlite3.connect("file:" + str(self.database.resolve()) + "?mode=ro", uri=True, timeout=3)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn

    def health(self) -> dict:
        with self._connect() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "mode": "read-only", "database_available": True}

    def summary(self) -> dict:
        with self._connect() as conn:
            states = {str(row["state"]): int(row["count"]) for row in conn.execute("SELECT state,COUNT(*) AS count FROM port_cases GROUP BY state")}
            numbers = int(conn.execute("SELECT COUNT(*) FROM port_numbers").fetchone()[0])
            documents = int(conn.execute("SELECT COUNT(*) FROM port_documents").fetchone()[0])
        return {"mode": "read-only", "cases": states, "numbers": numbers, "documents": documents, "submission_authorized": False, "cutover_authorized": False}

    def cases(self, *, state: str | None = None, limit: int = 50) -> list[dict]:
        if not 1 <= limit <= MAX_LIMIT:
            raise PortReadError("limit out of bounds")
        params: list[object] = []
        sql = "SELECT id,direction,state,customer_ref,losing_carrier,gaining_carrier,desired_due_date,foc_at_utc,scheduled_cutover_at_utc,external_reference,submission_authorized,cutover_authorized,created_at_utc,updated_at_utc FROM port_cases"
        if state:
            sql += " WHERE state=?"
            params.append(state)
        sql += " ORDER BY updated_at_utc DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["submission_authorized"] = bool(item["submission_authorized"])
            item["cutover_authorized"] = bool(item["cutover_authorized"])
            output.append(item)
        return output

    def case(self, case_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM port_cases WHERE id=?", (case_id,)).fetchone()
            if not row:
                raise PortReadError("port case not found")
            numbers = [dict(x) for x in conn.execute("SELECT number,status FROM port_numbers WHERE case_id=? ORDER BY number", (case_id,)).fetchall()]
            docs = [dict(x) for x in conn.execute("SELECT id,document_type,reference,sha256,received_at_utc FROM port_documents WHERE case_id=? ORDER BY received_at_utc,id", (case_id,)).fetchall()]
        item = dict(row)
        item["submission_authorized"] = bool(item["submission_authorized"])
        item["cutover_authorized"] = bool(item["cutover_authorized"])
        item["numbers"] = numbers
        item["documents"] = docs
        return item


class Handler(BaseHTTPRequestHandler):
    model: PortReadModel
    server_version = "WWCX-Portability/0.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/healthz":
                self.send_json(200, self.model.health()); return
            if parsed.path == "/api/portability/summary":
                self.send_json(200, self.model.summary()); return
            if parsed.path == "/api/portability/cases":
                raw = query.get("limit", ["50"])[0]
                try:
                    limit = int(raw)
                except ValueError as exc:
                    raise PortReadError("invalid limit") from exc
                self.send_json(200, {"items": self.model.cases(state=query.get("state", [None])[0], limit=limit)}); return
            if parsed.path.startswith("/api/portability/case/"):
                case_id = parsed.path.rsplit("/", 1)[-1]
                self.send_json(200, self.model.case(case_id)); return
            self.send_json(404, {"error": "not_found"})
        except (PortReadError, sqlite3.Error) as exc:
            self.send_json(503, {"error": "portability_unavailable", "detail": str(exc)[:200]})

    def _blocked(self) -> None:
        self.send_json(405, {"error": "read_only_surface", "port_submission_authorized": False, "cutover_authorized": False})

    do_POST = _blocked  # type: ignore[assignment]
    do_PUT = _blocked  # type: ignore[assignment]
    do_PATCH = _blocked  # type: ignore[assignment]
    do_DELETE = _blocked  # type: ignore[assignment]


def build_server(host: str, port: int, database: str | Path) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise PortReadError("portability service must remain loopback-only")
    if not 1024 <= port <= 65535:
        raise PortReadError("invalid port")
    model = PortReadModel(database)
    class BoundHandler(Handler):
        pass
    BoundHandler.model = model
    return ThreadingHTTPServer((host, port), BoundHandler)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--database", default="/var/lib/wwcx-portability/portability.sqlite3")
    args = parser.parse_args()
    server = build_server(args.host, args.port, args.database)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
