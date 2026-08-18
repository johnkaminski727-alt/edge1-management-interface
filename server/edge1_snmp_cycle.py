#!/usr/bin/env python3
"""One bounded Edge1 SNMP collection, inventory, alerting and retention cycle."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from edge1_snmp_platform import connect_db, get_device, load_config, poll_device, utcnow
from edge1_snmp_secure_exec import SecureNetSNMP
from edge1_snmp_services import AlertEngine, discover_interfaces, ensure_extended_schema, prune_retention, sync_interfaces


def _parse_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def due_device_ids(conn, now=None):
    now = now or datetime.now(timezone.utc)
    due = []
    for row in conn.execute("SELECT device_id,last_poll,polling_interval FROM devices WHERE polling_enabled=1"):
        last_poll = _parse_time(row["last_poll"])
        interval = max(10, min(int(row["polling_interval"] or 300), 86400))
        if last_poll is None or (now - last_poll).total_seconds() >= interval:
            due.append(row["device_id"])
    return due


async def run_cycle(db, config_path):
    config = load_config(config_path)
    conn = connect_db(db)
    ensure_extended_schema(conn)
    try:
        concurrency = max(1, min(int(config.get("polling", {}).get("concurrency", 16)), 256))
        semaphore = asyncio.Semaphore(concurrency)
        net = SecureNetSNMP()
        due = due_device_ids(conn)

        async def poll_one(device_id):
            async with semaphore:
                return await poll_device(conn, get_device(conn, device_id), net=net)

        poll_results = await asyncio.gather(*(poll_one(device_id) for device_id in due)) if due else []

        async def collect(device_id):
            async with semaphore:
                device = get_device(conn, device_id)
                if device["status"] != "online":
                    return {"device_id": device_id, "status": "skipped_offline"}
                try:
                    rows = await asyncio.to_thread(discover_interfaces, net, device)
                    count = sync_interfaces(conn, device_id, rows)
                    return {"device_id": device_id, "status": "ok", "interfaces": count}
                except Exception as exc:
                    return {"device_id": device_id, "status": "error", "error": str(exc)[:500]}

        interface_results = await asyncio.gather(*(collect(row["device_id"]) for row in poll_results)) if poll_results else []
        alerts = AlertEngine(conn).evaluate()
        retention = prune_retention(conn, config)
        return {
            "generated_at": utcnow(),
            "due_devices": len(due),
            "poll": poll_results,
            "interfaces": interface_results,
            "alerts": alerts,
            "retention_deleted": retention,
        }
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("EDGE1_SNMP_DB", "/var/lib/edge1-snmp/snmp.sqlite3")))
    parser.add_argument("--config", type=Path, default=Path(os.environ.get("EDGE1_SNMP_CONFIG", "/etc/edge1-snmp/config.json")))
    args = parser.parse_args()
    result = asyncio.run(run_cycle(args.db, args.config))
    print(json.dumps(result, sort_keys=True))
    return 0 if all(item.get("status") != "error" for item in result["interfaces"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
