#!/usr/bin/env python3
"""Loopback-only read surface for the Ava Office dashboard.

This service opens the office-manager SQLite database in immutable read-only mode and
exposes only bounded GET endpoints. It does not create the database, mutate work, approve
actions, contact providers, expose proposal parameter payloads, or read call audio.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    from .ava_call_archive import AvaCallArchiveError, AvaCallArchiveReadModel
except ImportError:  # immutable flat runtime
    from ava_call_archive import AvaCallArchiveError, AvaCallArchiveReadModel

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8116
DEFAULT_CALL_ARCHIVE = "/var/lib/wwcx-ava-office-manager/call-archive"
MAX_LIMIT = 100
MAX_TRANSCRIPT_CHARS = 100_000
ALLOWED_STATES = {"new", "working", "waiting_external", "needs_owner", "scheduled", "completed", "cancelled"}


class AvaOfficeReadError(RuntimeError):
    pass


class AvaOfficeReadModel:
    def __init__(self, database: str | Path) -> None:
        self.database = Path(database)

    def _connect(self) -> sqlite3.Connection:
        if not self.database.is_file():
            raise AvaOfficeReadError("office-manager database is unavailable")
        uri = "file:" + str(self.database.resolve()) + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=3)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn

    @staticmethod
    def _limit(raw: str | None, default: int = 50) -> int:
        if raw is None:
            return default
        try:
            value = int(raw)
        except ValueError as exc:
            raise AvaOfficeReadError("limit is invalid") from exc
        if not 1 <= value <= MAX_LIMIT:
            raise AvaOfficeReadError("limit is out of bounds")
        return value

    def health(self) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "mode": "read-only", "database_available": True}

    def summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            work = {str(row["state"]): int(row["count"]) for row in conn.execute("SELECT state,COUNT(*) AS count FROM work_items GROUP BY state")}
            actions = {str(row["status"]): int(row["count"]) for row in conn.execute("SELECT status,COUNT(*) AS count FROM action_proposals GROUP BY status")}
            instructions = int(conn.execute("SELECT COUNT(*) FROM standing_instructions WHERE enabled=1").fetchone()[0])
        return {
            "mode": "read-only",
            "work_items": work,
            "actions": actions,
            "standing_instructions": instructions,
        }

    def work_items(self, *, state: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if state is not None and state not in ALLOWED_STATES:
            raise AvaOfficeReadError("state filter is invalid")
        sql = "SELECT id,title,desired_outcome,state,priority,source_channel,owner,due_at_utc,created_at_utc,updated_at_utc FROM work_items"
        params: list[Any] = []
        if state is not None:
            sql += " WHERE state=?"
            params.append(state)
        sql += " ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,updated_at_utc DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def decisions(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id,work_item_id,capability,summary,authority_class,authorization,executable,reason,status,created_at_utc,updated_at_utc "
                "FROM action_proposals WHERE status IN ('awaiting_confirmation','blocked','approved') "
                "ORDER BY CASE status WHEN 'awaiting_confirmation' THEN 0 WHEN 'blocked' THEN 1 ELSE 2 END,updated_at_utc DESC LIMIT ?",
                (limit,),
            ).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["executable"] = bool(item["executable"])
            output.append(item)
        return output

    def executive_summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            team={str(r["health_state"]):int(r["count"]) for r in conn.execute("SELECT health_state,COUNT(*) count FROM executive_team_members WHERE active=1 GROUP BY health_state")}
            departments={str(r["department"]):int(r["count"]) for r in conn.execute("SELECT department,COUNT(*) count FROM executive_team_members WHERE active=1 GROUP BY department ORDER BY department")}
            assignments={str(r["state"]):int(r["count"]) for r in conn.execute("SELECT state,COUNT(*) count FROM executive_assignments GROUP BY state")}
            attention=int(conn.execute("SELECT COUNT(*) FROM executive_team_members WHERE active=1 AND health_state IN ('attention','failed','error','critical','degraded','unhealthy')").fetchone()[0])
            recent=int(conn.execute("SELECT COUNT(*) FROM executive_reports WHERE created_at_utc>=datetime('now','-24 hours')").fetchone()[0])
        return {"role":"CEO / Executive Orchestrator","coordination_authority":True,"generic_execution_authority":False,"team_health":team,"departments":departments,"assignments":assignments,"attention_reports":attention,"reports_24h":recent}

    def team(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows=conn.execute("SELECT member_id,display_name,department,role,service_unit,timer_unit,action_level,authority_ceiling,active,health_state,last_checkin_at_utc,last_report_id,updated_at_utc FROM executive_team_members WHERE active=1 ORDER BY CASE health_state WHEN 'attention' THEN 0 WHEN 'failed' THEN 0 WHEN 'error' THEN 0 WHEN 'healthy' THEN 2 ELSE 1 END,department,display_name LIMIT ?",(limit,)).fetchall()
        out=[]
        for row in rows:
            d=dict(row); d['active']=bool(d['active']); out.append(d)
        return out

    def assignments(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows=conn.execute("SELECT a.id,a.work_item_id,a.member_id,m.display_name,a.objective,a.state,a.priority,a.requested_by,a.created_at_utc,a.updated_at_utc FROM executive_assignments a JOIN executive_team_members m ON m.member_id=a.member_id ORDER BY CASE a.state WHEN 'failed' THEN 0 WHEN 'review' THEN 1 WHEN 'working' THEN 2 WHEN 'waiting' THEN 3 ELSE 4 END,a.updated_at_utc DESC LIMIT ?",(limit,)).fetchall()
        return [dict(r) for r in rows]

    def executive_reports(self, *, attention_only: bool = False, limit: int = 100) -> list[dict[str, Any]]:
        sql="SELECT r.id,r.member_id,m.display_name,m.department,r.assignment_id,r.report_type,r.health_state,r.summary,r.needs_attention,r.severity,r.source_ref,r.created_at_utc FROM executive_reports r JOIN executive_team_members m ON m.member_id=r.member_id"
        if attention_only:
            sql+=" WHERE r.needs_attention=1 AND r.id=(SELECT r2.id FROM executive_reports r2 WHERE r2.member_id=r.member_id ORDER BY r2.created_at_utc DESC,r2.rowid DESC LIMIT 1)"
        sql+=" ORDER BY r.created_at_utc DESC LIMIT ?"
        with self._connect() as conn: rows=conn.execute(sql,(limit,)).fetchall()
        out=[]
        for row in rows:
            d=dict(row); d['needs_attention']=bool(d['needs_attention']); out.append(d)
        return out

    def workflows(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            runs=conn.execute("SELECT id,workflow_id,trigger_type,trigger_ref,state,requested_by,work_item_id,created_at_utc,updated_at_utc,completed_at_utc,error_summary FROM executive_workflow_runs ORDER BY created_at_utc DESC LIMIT ?",(limit,)).fetchall()
            out=[]
            for row in runs:
                item=dict(row)
                steps=conn.execute("SELECT step_key,capability,member_id,state,attempt_count,started_at_utc,finished_at_utc,error_summary FROM executive_workflow_steps WHERE run_id=? ORDER BY created_at_utc,step_key",(item['id'],)).fetchall()
                item['steps']=[dict(s) for s in steps]
                out.append(item)
        return out

    def instructions(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id,domain,statement,effect,priority,created_at_utc,updated_at_utc FROM standing_instructions WHERE enabled=1 ORDER BY priority DESC,updated_at_utc DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]


class AvaOfficeHandler(BaseHTTPRequestHandler):
    read_model: AvaOfficeReadModel
    call_archive: AvaCallArchiveReadModel
    server_version = "WWCX-AvaOffice/0.2"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _bounded_int(raw: str | None, *, default: int, maximum: int, label: str) -> int:
        if raw is None:
            return default
        try:
            value = int(raw)
        except ValueError as exc:
            raise AvaOfficeReadError(f"{label} is invalid") from exc
        if not 1 <= value <= maximum:
            raise AvaOfficeReadError(f"{label} is out of bounds")
        return value

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query, keep_blank_values=False)
        try:
            if parsed.path == "/healthz":
                payload = self.read_model.health()
                payload["call_archive"] = self.call_archive.health()
                self._json(200, payload)
                return
            if parsed.path == "/api/ava-office/summary":
                self._json(200, self.read_model.summary())
                return
            if parsed.path == "/api/ava-office/executive":
                self._json(200, self.read_model.executive_summary())
                return
            if parsed.path == "/api/ava-office/team":
                limit = self.read_model._limit(query.get("limit", [None])[0], default=100)
                self._json(200, {"items": self.read_model.team(limit=limit)})
                return
            if parsed.path == "/api/ava-office/assignments":
                limit = self.read_model._limit(query.get("limit", [None])[0], default=100)
                self._json(200, {"items": self.read_model.assignments(limit=limit)})
                return
            if parsed.path == "/api/ava-office/reports":
                limit = self.read_model._limit(query.get("limit", [None])[0], default=100)
                attention = query.get("attention", ["0"])[0] in {"1","true","yes"}
                self._json(200, {"items": self.read_model.executive_reports(attention_only=attention, limit=limit)})
                return
            if parsed.path == "/api/ava-office/workflows":
                limit = self.read_model._limit(query.get("limit", [None])[0], default=100)
                self._json(200, {"items": self.read_model.workflows(limit=limit)})
                return
            if parsed.path == "/api/ava-office/work-items":
                state = query.get("state", [None])[0]
                limit = self.read_model._limit(query.get("limit", [None])[0])
                self._json(200, {"items": self.read_model.work_items(state=state, limit=limit)})
                return
            if parsed.path == "/api/ava-office/decisions":
                limit = self.read_model._limit(query.get("limit", [None])[0])
                self._json(200, {"items": self.read_model.decisions(limit=limit)})
                return
            if parsed.path == "/api/ava-office/instructions":
                limit = self.read_model._limit(query.get("limit", [None])[0], default=100)
                self._json(200, {"items": self.read_model.instructions(limit=limit)})
                return
            if parsed.path == "/api/ava-office/call-archive/health":
                self._json(200, self.call_archive.health())
                return
            if parsed.path == "/api/ava-office/calls":
                limit = self.read_model._limit(query.get("limit", [None])[0])
                self._json(200, {"items": self.call_archive.calls(limit=limit)})
                return
            if parsed.path == "/api/ava-office/voicemails":
                limit = self.read_model._limit(query.get("limit", [None])[0])
                self._json(200, {"items": self.call_archive.voicemails(limit=limit)})
                return
            if parsed.path == "/api/ava-office/transcript":
                call_ref = query.get("call_ref", [None])[0]
                if not call_ref:
                    raise AvaOfficeReadError("call_ref is required")
                max_chars = self._bounded_int(
                    query.get("max_chars", [None])[0],
                    default=20_000,
                    maximum=MAX_TRANSCRIPT_CHARS,
                    label="max_chars",
                )
                self._json(200, self.call_archive.transcript(call_ref, max_chars=max_chars))
                return
            self._json(404, {"error": "not_found"})
        except AvaCallArchiveError as exc:
            self._json(503, {"error": "call_archive_unavailable", "detail": str(exc)[:200]})
        except (AvaOfficeReadError, sqlite3.Error) as exc:
            self._json(503, {"error": "office_manager_unavailable", "detail": str(exc)[:200]})

    def _method_not_allowed(self) -> None:
        self._json(405, {"error": "read_only_surface", "mutation_authorized": False})

    do_POST = _method_not_allowed  # type: ignore[assignment]
    do_PUT = _method_not_allowed  # type: ignore[assignment]
    do_PATCH = _method_not_allowed  # type: ignore[assignment]
    do_DELETE = _method_not_allowed  # type: ignore[assignment]


def build_server(
    host: str,
    port: int,
    database: str | Path,
    call_archive_root: str | Path = DEFAULT_CALL_ARCHIVE,
) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise AvaOfficeReadError("Ava Office read surface must remain loopback-only")
    if not isinstance(port, int) or isinstance(port, bool) or not 1024 <= port <= 65535:
        raise AvaOfficeReadError("port is invalid")
    read_model = AvaOfficeReadModel(database)
    call_archive = AvaCallArchiveReadModel(call_archive_root)

    class BoundHandler(AvaOfficeHandler):
        pass

    BoundHandler.read_model = read_model
    BoundHandler.call_archive = call_archive
    return ThreadingHTTPServer((host, port), BoundHandler)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--database", default="/var/lib/wwcx-ava-office-manager/office-manager.sqlite3")
    parser.add_argument("--call-archive", default=DEFAULT_CALL_ARCHIVE)
    args = parser.parse_args()
    server = build_server(args.host, args.port, args.database, args.call_archive)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
