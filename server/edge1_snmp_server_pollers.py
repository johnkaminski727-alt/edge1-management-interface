#!/usr/bin/env python3
"""Host-native server telemetry for WW.CX SNMP Operations.

This module is intentionally separate from genuine SNMP device polling. It
collects bounded host metrics without running an SNMP agent or opening UDP
161/162, and stores them in dedicated server_poller/server_metric tables.

The collector is Python 3.6 compatible so the same file can run under a cPanel
shared-host account. Edge1 may also ingest copied JSONL snapshots later; the
transfer mechanism is deliberately out of scope and must remain authenticated.
"""
from __future__ import print_function

import argparse
import datetime
import json
import math
import os
import platform
import re
import shutil
import sqlite3
import tempfile
import uuid

SCHEMA = "wwcx.snmp-server-poller.v1"
DEFAULT_DB = os.environ.get("EDGE1_SNMP_DB", "/var/lib/edge1-snmp/snmp.sqlite3")
POLL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")
METRICS = {
    "cpu_count": "count",
    "load_1m": "load",
    "load_5m": "load",
    "load_15m": "load",
    "uptime_seconds": "seconds",
    "memory_total_bytes": "bytes",
    "memory_available_bytes": "bytes",
    "memory_used_percent": "percent",
    "disk_total_bytes": "bytes",
    "disk_free_bytes": "bytes",
    "disk_used_percent": "percent",
    "process_count": "count",
}


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _safe_id(value, label):
    text = str(value or "").strip()
    if not POLL_ID_RE.match(text):
        raise ValueError("invalid %s" % label)
    return text


def _safe_host(value):
    text = str(value or "").strip()
    if not HOST_RE.match(text):
        raise ValueError("invalid observer host")
    return text


def _read_text(path):
    with open(path, "r") as handle:
        return handle.read().strip()


def _read_load(proc_root):
    parts = _read_text(os.path.join(proc_root, "loadavg")).split()
    if len(parts) < 3:
        raise ValueError("/proc/loadavg is incomplete")
    return [float(parts[0]), float(parts[1]), float(parts[2])]


def _read_uptime(proc_root):
    return float(_read_text(os.path.join(proc_root, "uptime")).split()[0])


def _read_meminfo(proc_root):
    values = {}
    with open(os.path.join(proc_root, "meminfo"), "r") as handle:
        for raw in handle:
            if ":" not in raw:
                continue
            key, rest = raw.split(":", 1)
            fields = rest.strip().split()
            if not fields:
                continue
            try:
                amount = float(fields[0])
            except ValueError:
                continue
            if len(fields) > 1 and fields[1].lower() == "kb":
                amount *= 1024.0
            values[key] = amount
    total = values.get("MemTotal")
    available = values.get("MemAvailable", values.get("MemFree"))
    if total is None or available is None or total <= 0:
        raise ValueError("/proc/meminfo lacks usable memory totals")
    used_percent = max(0.0, min(100.0, ((total - available) / total) * 100.0))
    return total, available, used_percent


def _process_count(proc_root):
    try:
        return sum(1 for name in os.listdir(proc_root) if name.isdigit())
    except OSError:
        return None


def collect_snapshot(poller_id, display_name, observer_host=None, disk_path="/", proc_root="/proc"):
    poller_id = _safe_id(poller_id, "poller id")
    observer_host = _safe_host(observer_host or platform.node() or poller_id)
    display_name = str(display_name or observer_host).strip()[:160]
    if not display_name:
        raise ValueError("display name is required")

    load_1m, load_5m, load_15m = _read_load(proc_root)
    uptime = _read_uptime(proc_root)
    mem_total, mem_available, mem_used = _read_meminfo(proc_root)
    disk = shutil.disk_usage(disk_path)
    disk_used_percent = 0.0 if disk.total <= 0 else ((disk.total - disk.free) / float(disk.total)) * 100.0

    metrics = {
        "cpu_count": float(os.cpu_count() or 0),
        "load_1m": load_1m,
        "load_5m": load_5m,
        "load_15m": load_15m,
        "uptime_seconds": uptime,
        "memory_total_bytes": mem_total,
        "memory_available_bytes": mem_available,
        "memory_used_percent": mem_used,
        "disk_total_bytes": float(disk.total),
        "disk_free_bytes": float(disk.free),
        "disk_used_percent": max(0.0, min(100.0, disk_used_percent)),
    }
    processes = _process_count(proc_root)
    if processes is not None:
        metrics["process_count"] = float(processes)

    return {
        "schema": SCHEMA,
        "generated_at": utcnow(),
        "poller_id": poller_id,
        "display_name": display_name,
        "observer_host": observer_host,
        "source_type": "host-native",
        "metrics": metrics,
    }


def validate_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    if snapshot.get("schema") != SCHEMA:
        raise ValueError("unsupported server poller snapshot schema")
    _safe_id(snapshot.get("poller_id"), "poller id")
    _safe_host(snapshot.get("observer_host"))
    generated_at = str(snapshot.get("generated_at") or "")
    if len(generated_at) < 20 or len(generated_at) > 64:
        raise ValueError("invalid generated_at")
    display_name = str(snapshot.get("display_name") or "").strip()
    if not display_name or len(display_name) > 160:
        raise ValueError("invalid display name")
    if snapshot.get("source_type") != "host-native":
        raise ValueError("unsupported source_type")
    metrics = snapshot.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        raise ValueError("metrics are required")
    unknown = set(metrics) - set(METRICS)
    if unknown:
        raise ValueError("unsupported metric(s): %s" % ",".join(sorted(unknown)))
    normalized = {}
    for name, value in metrics.items():
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            raise ValueError("metric %s must be numeric" % name)
        if not math.isfinite(numeric):
            raise ValueError("metric %s must be finite" % name)
        if name.endswith("_percent") and not 0.0 <= numeric <= 100.0:
            raise ValueError("metric %s must be 0..100" % name)
        if name in {"cpu_count", "uptime_seconds", "memory_total_bytes", "memory_available_bytes", "disk_total_bytes", "disk_free_bytes", "process_count"} and numeric < 0:
            raise ValueError("metric %s must be non-negative" % name)
        normalized[name] = numeric
    return normalized


def connect(path=DEFAULT_DB):
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    ensure_schema(conn)
    return conn


def ensure_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS server_pollers (
          poller_id TEXT PRIMARY KEY,
          display_name TEXT NOT NULL,
          observer_host TEXT NOT NULL,
          source_type TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'unknown',
          last_poll TEXT,
          last_success TEXT,
          last_error TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS server_metrics (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts TEXT NOT NULL,
          poller_id TEXT NOT NULL,
          name TEXT NOT NULL,
          value_num REAL NOT NULL,
          unit TEXT,
          source TEXT NOT NULL DEFAULT 'host-native',
          FOREIGN KEY(poller_id) REFERENCES server_pollers(poller_id) ON DELETE CASCADE,
          UNIQUE(poller_id, ts, name, source)
        );
        CREATE INDEX IF NOT EXISTS idx_server_metrics_poller_ts
          ON server_metrics(poller_id, ts);
        """
    )
    conn.commit()


def _audit(conn, action, target, reason, result, after=None):
    present = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit'").fetchone()
    if not present:
        return
    conn.execute(
        "INSERT INTO audit VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            str(uuid.uuid4()), utcnow(), "edge1-snmp-server-poller", "server-poller",
            action, target, reason, "{}", json.dumps(after or {}, sort_keys=True),
            result, None, "none", "{}",
        ),
    )


def ingest_snapshot(conn, snapshot, import_source="local"):
    metrics = validate_snapshot(snapshot)
    poller_id = snapshot["poller_id"]
    now = utcnow()
    generated_at = snapshot["generated_at"]
    existing = conn.execute("SELECT poller_id FROM server_pollers WHERE poller_id=?", (poller_id,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE server_pollers SET display_name=?,observer_host=?,source_type=?,status='online',last_poll=?,last_success=?,last_error=NULL,updated_at=? WHERE poller_id=?",
            (snapshot["display_name"], snapshot["observer_host"], snapshot["source_type"], generated_at, generated_at, now, poller_id),
        )
    else:
        conn.execute(
            "INSERT INTO server_pollers(poller_id,display_name,observer_host,source_type,status,last_poll,last_success,last_error,created_at,updated_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (poller_id, snapshot["display_name"], snapshot["observer_host"], snapshot["source_type"], "online", generated_at, generated_at, None, now, now, "{}"),
        )
    inserted = 0
    for name, value in sorted(metrics.items()):
        cur = conn.execute(
            "INSERT OR IGNORE INTO server_metrics(ts,poller_id,name,value_num,unit,source) VALUES(?,?,?,?,?,?)",
            (generated_at, poller_id, name, value, METRICS[name], import_source),
        )
        inserted += int(cur.rowcount > 0)
    _audit(conn, "server.snapshot.ingest", poller_id, "host-native server telemetry", "succeeded", {"sample_count": inserted, "source": import_source})
    conn.commit()
    return {"poller_id": poller_id, "status": "online", "samples_inserted": inserted, "generated_at": generated_at}


def record_error(conn, poller_id, display_name, observer_host, message):
    poller_id = _safe_id(poller_id, "poller id")
    observer_host = _safe_host(observer_host)
    now = utcnow()
    text = str(message or "collection failed")[-500:]
    exists = conn.execute("SELECT poller_id FROM server_pollers WHERE poller_id=?", (poller_id,)).fetchone()
    if exists:
        conn.execute("UPDATE server_pollers SET status='error',last_poll=?,last_error=?,updated_at=? WHERE poller_id=?", (now, text, now, poller_id))
    else:
        conn.execute(
            "INSERT INTO server_pollers(poller_id,display_name,observer_host,source_type,status,last_poll,last_success,last_error,created_at,updated_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (poller_id, display_name[:160], observer_host, "host-native", "error", now, None, text, now, now, "{}"),
        )
    _audit(conn, "server.poll", poller_id, "host-native server telemetry", "failed", {"error": text})
    conn.commit()


def poll_local(conn, poller_id, display_name, observer_host=None, disk_path="/", proc_root="/proc"):
    observer_host = observer_host or platform.node() or poller_id
    try:
        snapshot = collect_snapshot(poller_id, display_name, observer_host, disk_path=disk_path, proc_root=proc_root)
        result = ingest_snapshot(conn, snapshot, import_source="local")
        _audit(conn, "server.poll", poller_id, "host-native local collection", "succeeded", {"sample_count": result["samples_inserted"]})
        conn.commit()
        return result
    except Exception as exc:
        record_error(conn, poller_id, display_name, observer_host, exc)
        raise


def ingest_jsonl(conn, path, max_records=10000):
    if not os.path.isfile(path):
        return {"path": path, "status": "absent", "records": 0, "samples_inserted": 0}
    records = 0
    samples = 0
    with open(path, "r") as handle:
        lines = handle.readlines()[-max_records:]
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        snapshot = json.loads(raw)
        result = ingest_snapshot(conn, snapshot, import_source="copied-jsonl")
        records += 1
        samples += result["samples_inserted"]
    return {"path": path, "status": "ok", "records": records, "samples_inserted": samples}


def prune_metrics(conn, retention_days=30):
    days = max(1, min(int(retention_days), 3650))
    cur = conn.execute("DELETE FROM server_metrics WHERE ts < datetime('now', ?)", ("-%d days" % days,))
    conn.commit()
    return cur.rowcount


def list_pollers(conn):
    ensure_schema(conn)
    rows = []
    for row in conn.execute("SELECT * FROM server_pollers ORDER BY display_name"):
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        rows.append(item)
    return rows


def list_metrics(conn, poller_id, limit=500):
    poller_id = _safe_id(poller_id, "poller id")
    limit = max(1, min(int(limit), 5000))
    return [dict(row) for row in conn.execute("SELECT * FROM server_metrics WHERE poller_id=? ORDER BY ts DESC,id DESC LIMIT ?", (poller_id, limit))]


def health(conn):
    ensure_schema(conn)
    total = conn.execute("SELECT count(*) FROM server_pollers").fetchone()[0]
    online = conn.execute("SELECT count(*) FROM server_pollers WHERE status='online'").fetchone()[0]
    errors = conn.execute("SELECT count(*) FROM server_pollers WHERE status='error'").fetchone()[0]
    return {"server_pollers": total, "server_pollers_online": online, "server_pollers_error": errors}


def append_jsonl(path, snapshot, max_records=10000):
    validate_snapshot(snapshot)
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, 0o700)
    line = json.dumps(snapshot, sort_keys=True, separators=(",", ":")) + "\n"
    old = []
    if os.path.isfile(path):
        with open(path, "r") as handle:
            old = handle.readlines()
    keep = old[-max(0, int(max_records) - 1):] if max_records > 1 else []
    fd, temporary = tempfile.mkstemp(prefix=".server-poller-", dir=directory)
    try:
        with os.fdopen(fd, "w") as handle:
            for raw in keep:
                handle.write(raw)
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def _env_paths():
    raw = os.environ.get("EDGE1_SNMP_SERVER_POLLER_IMPORT_PATHS", "")
    return [part for part in raw.split(":") if part]


def main():
    parser = argparse.ArgumentParser(description="WW.CX SNMP host-native server pollers")
    parser.add_argument("--db", default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="command")

    collect = sub.add_parser("collect")
    collect.add_argument("--poller-id", required=True)
    collect.add_argument("--display-name", required=True)
    collect.add_argument("--observer-host")
    collect.add_argument("--disk-path", default=os.environ.get("HOME", "/"))
    collect.add_argument("--proc-root", default="/proc")
    collect.add_argument("--output", default="-")
    collect.add_argument("--max-records", type=int, default=10000)

    local = sub.add_parser("poll-local")
    local.add_argument("--poller-id", required=True)
    local.add_argument("--display-name", required=True)
    local.add_argument("--observer-host")
    local.add_argument("--disk-path", default="/")
    local.add_argument("--proc-root", default="/proc")
    local.add_argument("--import-path", action="append", default=[])
    local.add_argument("--retention-days", type=int, default=30)

    ingest = sub.add_parser("ingest")
    ingest.add_argument("--input", required=True)

    sub.add_parser("list")
    args = parser.parse_args()
    if not args.command:
        parser.error("a command is required")

    if args.command == "collect":
        snapshot = collect_snapshot(args.poller_id, args.display_name, args.observer_host, args.disk_path, args.proc_root)
        if args.output == "-":
            print(json.dumps(snapshot, sort_keys=True))
        else:
            append_jsonl(args.output, snapshot, max_records=args.max_records)
            print(json.dumps({"status": "ok", "output": args.output, "generated_at": snapshot["generated_at"]}, sort_keys=True))
        return 0

    conn = connect(args.db)
    try:
        if args.command == "poll-local":
            local_result = poll_local(conn, args.poller_id, args.display_name, args.observer_host, args.disk_path, args.proc_root)
            imports = []
            for path in list(args.import_path) + _env_paths():
                imports.append(ingest_jsonl(conn, path))
            deleted = prune_metrics(conn, args.retention_days)
            print(json.dumps({"local": local_result, "imports": imports, "retention_deleted": deleted, "health": health(conn)}, sort_keys=True))
            return 0
        if args.command == "ingest":
            print(json.dumps(ingest_jsonl(conn, args.input), sort_keys=True))
            return 0
        if args.command == "list":
            print(json.dumps({"pollers": list_pollers(conn), "health": health(conn)}, sort_keys=True))
            return 0
    finally:
        conn.close()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
