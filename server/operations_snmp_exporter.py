#!/usr/bin/env python3
"""Export sanitized Edge1 SNMP Operations Center status JSON."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from edge1_snmp_platform import connect_db, utcnow
from edge1_snmp_services import ensure_extended_schema


def build(conn):
    ensure_extended_schema(conn)
    managed = conn.execute("SELECT count(*) FROM devices").fetchone()[0]
    status_counts = {
        row["status"]: row["n"]
        for row in conn.execute("SELECT status,count(*) n FROM devices GROUP BY status")
    }
    versions = {
        row["snmp_version"]: row["n"]
        for row in conn.execute("SELECT snmp_version,count(*) n FROM devices GROUP BY snmp_version")
    }
    active_alerts = conn.execute("SELECT count(*) FROM alerts WHERE state='open'").fetchone()[0]
    critical = conn.execute("SELECT count(*) FROM alerts WHERE state='open' AND severity='critical'").fetchone()[0]
    warning = conn.execute("SELECT count(*) FROM alerts WHERE state='open' AND severity='warning'").fetchone()[0]
    recent_events = [
        dict(row) for row in conn.execute(
            "SELECT event_id,ts,source_address,device_id,trap_oid,severity,event_type,correlation_id "
            "FROM events ORDER BY ts DESC LIMIT 20"
        )
    ]
    devices = [
        dict(row) for row in conn.execute(
            "SELECT device_id,display_name,hostname,management_address,device_type,vendor,model,site,location,"
            "tags_json,environment,snmp_version,snmp_port,polling_enabled,polling_interval,trap_enabled,write_enabled,"
            "timezone,status,last_seen,last_poll,last_success,last_error FROM devices ORDER BY display_name"
        )
    ]
    interfaces = [
        dict(row) for row in conn.execute(
            "SELECT device_id,if_index,if_name,if_descr,if_alias,if_type,admin_status,oper_status,speed_bps,last_seen "
            "FROM interfaces ORDER BY device_id,if_index LIMIT 1000"
        )
    ]
    latest_errors = [
        dict(row) for row in conn.execute(
            "SELECT device_id,name,value_num,ts FROM metrics "
            "WHERE name IN ('ifInErrors','ifOutErrors') AND value_num IS NOT NULL "
            "ORDER BY value_num DESC,ts DESC LIMIT 10"
        )
    ]
    poll_attempted = conn.execute("SELECT count(*) FROM devices WHERE last_poll IS NOT NULL").fetchone()[0]
    poll_ok = conn.execute(
        "SELECT count(*) FROM devices WHERE last_poll IS NOT NULL AND last_success IS NOT NULL "
        "AND (last_error IS NULL OR status='online')"
    ).fetchone()[0]
    rate = round((poll_ok / poll_attempted) * 100, 2) if poll_attempted else None
    anomalies = [
        dict(row) for row in conn.execute(
            "SELECT alert_id,updated_at,device_id,severity,policy,summary,correlation_id "
            "FROM alerts WHERE state='open' ORDER BY updated_at DESC LIMIT 20"
        )
    ]
    return {
        "generated_at": utcnow(),
        "managed_devices": managed,
        "online_devices": status_counts.get("online", 0),
        "offline_devices": status_counts.get("offline", 0),
        "warning_devices": warning,
        "critical_devices": critical,
        "active_alerts": active_alerts,
        "recent_traps": recent_events,
        "poll_success_rate_percent": rate,
        "snmp_version_distribution": versions,
        "highest_error_metrics": latest_errors,
        "devices": devices,
        "interfaces": interfaces,
        "ai_anomalies": anomalies,
    }


def atomic_write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    os.close(fd)
    temp_path = Path(temporary)
    try:
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(temp_path, 0o644)
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(os.environ.get("EDGE1_SNMP_DB", "/var/lib/edge1-snmp/snmp.sqlite3")),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(os.environ.get("EDGE1_SNMP_STATUS_OUTPUT", "/var/www/edge1-status/operations-snmp.json")),
    )
    args = parser.parse_args()
    conn = connect_db(args.db)
    try:
        payload = build(conn)
    finally:
        conn.close()
    atomic_write(args.output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
