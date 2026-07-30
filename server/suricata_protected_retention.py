#!/usr/bin/env python3
"""Root-only bounded retention for sanitized Suricata alerts.

The committed policy remains disabled. Tests and future authorized deployment may
supply an enabled policy explicitly; this module never reads raw Suricata EVE.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sqlite3
import stat
import tempfile
from pathlib import Path
from typing import Any

POLICY = Path("/opt/edge1-management-interface/config/security/suricata-protected-retention-policy.json")
ALLOWED_STATES = {"disabled", "healthy", "capacity_limited", "source_unavailable", "schema_rejected", "storage_error"}
RISK_VALUES = {"critical", "high", "medium", "low", "info", "unknown"}
TEXT_LIMITS = {
    "timestamp": 128, "signature": 512, "risk": 40, "category": 256,
    "action": 64, "source": 128, "destination": 128, "protocol": 32,
    "application_protocol": 64, "event_id": 128,
}
INTEGER_LIMITS = {
    "severity": (0, 255), "source_port": (1, 65535),
    "destination_port": (1, 65535), "signature_id": (0, None),
    "generator_id": (0, None), "revision": (0, None), "flow_id": (0, None),
}


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat()


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def load_policy(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("contract") != "wwcx.suricata-protected-retention-policy.v1":
        raise ValueError("unsupported retention policy contract")
    return data


def clean_text(value: Any, maximum: int) -> str | None:
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    text = str(value).replace("\x00", "").strip()
    return text[:maximum] or None


def clean_int(value: Any, minimum: int, maximum: int | None) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < minimum or (maximum is not None and number > maximum):
        return None
    return number


def severity_risk(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value <= 0:
        return "critical"
    if value == 1:
        return "high"
    if value == 2:
        return "medium"
    if value == 3:
        return "low"
    return "info"


def validate_alert(raw: Any, policy: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    approved = set(policy["privacy"]["approved_fields"])
    if set(raw) - approved:
        return None
    result: dict[str, Any] = {}
    for field in approved:
        value = raw.get(field)
        if field in TEXT_LIMITS:
            result[field] = clean_text(value, TEXT_LIMITS[field])
        elif field in INTEGER_LIMITS:
            result[field] = clean_int(value, *INTEGER_LIMITS[field])
        else:
            return None
    event_time = parse_time(result.get("timestamp"))
    if event_time is None:
        return None
    result["timestamp"] = iso(event_time)
    if not result.get("signature"):
        result["signature"] = "Unknown"
    risk = clean_text(result.get("risk"), 40)
    if risk is None or risk.lower() not in RISK_VALUES:
        risk = severity_risk(result.get("severity"))
    result["risk"] = risk.lower()
    return {field: result.get(field) for field in policy["privacy"]["approved_fields"]}


def event_key(alert: dict[str, Any], policy: dict[str, Any]) -> str:
    canonical = {field: alert.get(field) for field in policy["ingest"]["deduplication"]["canonical_fields"]}
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def connect(database: Path, policy: dict[str, Any]) -> sqlite3.Connection:
    database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(database.parent, 0o700)
    conn = sqlite3.connect(database)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute(f"PRAGMA page_size={int(policy['storage']['page_size_bytes'])}")
    conn.execute(f"PRAGMA max_page_count={int(policy['storage']['max_page_count'])}")
    conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS alerts (
            event_key TEXT PRIMARY KEY,
            event_time TEXT NOT NULL,
            ingested_at TEXT NOT NULL,
            risk TEXT NOT NULL,
            signature_id INTEGER,
            flow_id TEXT,
            schema_version TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS alerts_event_time_idx ON alerts(event_time);
        CREATE INDEX IF NOT EXISTS alerts_risk_idx ON alerts(risk);
        CREATE INDEX IF NOT EXISTS alerts_signature_id_idx ON alerts(signature_id);
        CREATE TABLE IF NOT EXISTS ingest_runs (
            run_at TEXT NOT NULL,
            source_generated_at TEXT,
            accepted INTEGER NOT NULL,
            duplicate INTEGER NOT NULL,
            rejected INTEGER NOT NULL,
            pruned INTEGER NOT NULL,
            retained INTEGER NOT NULL,
            database_bytes INTEGER NOT NULL,
            state TEXT NOT NULL
        );
    """)
    conn.commit()
    os.chmod(database, 0o600)
    return conn


def database_bytes(conn: sqlite3.Connection) -> int:
    page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
    page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
    return page_count * page_size


def prune(conn: sqlite3.Connection, policy: dict[str, Any], now: dt.datetime) -> int:
    storage = policy["storage"]
    before = conn.total_changes
    cutoff = iso(now - dt.timedelta(days=int(storage["retention_days"])))
    conn.execute("DELETE FROM alerts WHERE event_time < ?", (cutoff,))
    count = int(conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0])
    excess = max(0, count - int(storage["max_events"]))
    if excess:
        conn.execute("DELETE FROM alerts WHERE event_key IN (SELECT event_key FROM alerts ORDER BY event_time ASC LIMIT ?)", (excess,))
    target_pages = int(int(storage["max_page_count"]) * int(storage["prune_target_percent"]) / 100)
    while int(conn.execute("PRAGMA page_count").fetchone()[0]) > target_pages:
        row = conn.execute("SELECT event_key FROM alerts ORDER BY event_time ASC LIMIT 1000").fetchall()
        if not row:
            break
        conn.executemany("DELETE FROM alerts WHERE event_key = ?", row)
        conn.execute("PRAGMA incremental_vacuum(1000)")
    conn.commit()
    return conn.total_changes - before


def atomic_json(path: Path, payload: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def status_payload(state: str, now: dt.datetime, **values: Any) -> dict[str, Any]:
    if state not in ALLOWED_STATES:
        raise ValueError("invalid state")
    return {
        "contract": "wwcx.suricata-protected-retention-status.v1",
        "generated_at": iso(now),
        "state": state,
        "read_only": True,
        "public_access": False,
        "network_listener": False,
        "raw_eve_accessed": False,
        "suricata_service_changed": False,
        "traffic_controls_changed": False,
        **values,
    }


def ingest(policy_path: Path, source_override: Path | None = None, database_override: Path | None = None, status_override: Path | None = None) -> dict[str, Any]:
    policy = load_policy(policy_path)
    now = utc_now()
    database = database_override or Path(policy["storage"]["database"])
    status = status_override or Path(policy["storage"]["status_file"])
    if not policy.get("enabled") or not policy["acceptance"].get("deployment_authorized"):
        payload = status_payload("disabled", now, accepted=0, duplicate=0, rejected=0, pruned=0, retained=0, database_bytes=0)
        atomic_json(status, payload)
        return payload
    source = source_override or Path(policy["ingest"]["source"])
    if not source.is_file():
        payload = status_payload("source_unavailable", now, accepted=0, duplicate=0, rejected=0, pruned=0, retained=0, database_bytes=0)
        atomic_json(status, payload)
        return payload
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = status_payload("schema_rejected", now, accepted=0, duplicate=0, rejected=0, pruned=0, retained=0, database_bytes=0)
        atomic_json(status, payload)
        return payload
    security = document.get("security") if isinstance(document, dict) else None
    alerts = security.get("recent_alerts") if isinstance(security, dict) else None
    if not isinstance(security, dict) or security.get("alert_schema") != policy["ingest"]["required_source_schema"] or not isinstance(alerts, list):
        payload = status_payload("schema_rejected", now, accepted=0, duplicate=0, rejected=0, pruned=0, retained=0, database_bytes=0)
        atomic_json(status, payload)
        return payload
    accepted = duplicate = rejected = 0
    try:
        conn = connect(database, policy)
        with conn:
            for raw in alerts[: int(policy["ingest"]["max_alerts_per_run"])]:
                alert = validate_alert(raw, policy)
                if alert is None:
                    rejected += 1
                    continue
                key = event_key(alert, policy)
                result = conn.execute(
                    "INSERT OR IGNORE INTO alerts(event_key,event_time,ingested_at,risk,signature_id,flow_id,schema_version,payload_json) VALUES(?,?,?,?,?,?,?,?)",
                    (key, alert["timestamp"], iso(now), alert["risk"], alert.get("signature_id"), str(alert.get("flow_id")) if alert.get("flow_id") is not None else None, policy["ingest"]["required_source_schema"], json.dumps(alert, sort_keys=True, separators=(",", ":"), ensure_ascii=False)),
                )
                if result.rowcount:
                    accepted += 1
                else:
                    duplicate += 1
        pruned = prune(conn, policy, now)
        retained = int(conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0])
        size = database_bytes(conn)
        state = "healthy"
        if size >= int(policy["storage"]["max_database_bytes"]) or retained >= int(policy["storage"]["max_events"]):
            state = "capacity_limited"
        conn.execute("INSERT INTO ingest_runs VALUES(?,?,?,?,?,?,?,?,?)", (iso(now), document.get("generated_at"), accepted, duplicate, rejected, pruned, retained, size, state))
        conn.commit()
        conn.close()
    except (OSError, sqlite3.Error):
        payload = status_payload("storage_error", now, accepted=accepted, duplicate=duplicate, rejected=rejected, pruned=0, retained=0, database_bytes=0)
        atomic_json(status, payload)
        return payload
    payload = status_payload(state, now, source_generated_at=document.get("generated_at"), accepted=accepted, duplicate=duplicate, rejected=rejected, pruned=pruned, retained=retained, database_bytes=size)
    atomic_json(status, payload)
    return payload


def query(policy_path: Path, database_override: Path | None, hours: int, limit: int) -> list[dict[str, Any]]:
    policy = load_policy(policy_path)
    maximum_hours = int(policy["query"]["max_window_days"]) * 24
    maximum_limit = int(policy["query"]["max_limit"])
    if hours < 1 or hours > maximum_hours or limit < 1 or limit > maximum_limit:
        raise ValueError("query exceeds policy bounds")
    database = database_override or Path(policy["storage"]["database"])
    if not database.is_file() or stat.S_IMODE(database.stat().st_mode) & 0o077:
        raise PermissionError("root-only database is missing or has unsafe permissions")
    cutoff = iso(utc_now() - dt.timedelta(hours=hours))
    conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    rows = conn.execute("SELECT payload_json FROM alerts WHERE event_time >= ? ORDER BY event_time DESC LIMIT ?", (cutoff, limit)).fetchall()
    conn.close()
    return [json.loads(row[0]) for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=POLICY)
    sub = parser.add_subparsers(dest="command", required=True)
    ingest_parser = sub.add_parser("ingest")
    ingest_parser.add_argument("--source", type=Path)
    ingest_parser.add_argument("--database", type=Path)
    ingest_parser.add_argument("--status", type=Path)
    query_parser = sub.add_parser("query")
    query_parser.add_argument("--database", type=Path)
    query_parser.add_argument("--hours", type=int)
    query_parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    policy = load_policy(args.policy)
    if args.command == "ingest":
        print(json.dumps(ingest(args.policy, args.source, args.database, args.status), indent=2, sort_keys=True))
    else:
        hours = args.hours or int(policy["query"]["default_window_hours"])
        limit = args.limit or int(policy["query"]["default_limit"])
        print(json.dumps(query(args.policy, args.database, hours, limit), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
