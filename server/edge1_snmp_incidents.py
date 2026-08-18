#!/usr/bin/env python3
"""Deterministic incident correlation for the Edge1 SNMP evidence layer."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from edge1_snmp_services import ensure_extended_schema


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def correlate_recent(conn, *, minutes: int = 15, now: datetime | None = None) -> list[dict[str, Any]]:
    """Correlate recent device failures, interface state and traps without fabricating topology.

    Confirmed topology links can raise confidence. Inferred links are kept as evidence
    but never promoted to confirmed facts.
    """
    ensure_extended_schema(conn)
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=max(1, min(minutes, 1440)))
    cutoff_text = cutoff.isoformat()
    events = [dict(r) for r in conn.execute(
        "SELECT * FROM events WHERE ts>=? ORDER BY ts", (cutoff_text,)
    )]
    offline = [dict(r) for r in conn.execute(
        "SELECT device_id,display_name,status,last_poll,last_success,last_error,updated_at "
        "FROM devices WHERE status='offline'"
    )]
    links = [dict(r) for r in conn.execute(
        "SELECT * FROM topology_links WHERE observed_at>=? OR confidence='confirmed'", (cutoff_text,)
    )]
    interfaces = [dict(r) for r in conn.execute(
        "SELECT device_id,if_index,if_name,if_descr,admin_status,oper_status,last_seen "
        "FROM interfaces WHERE admin_status=1 AND oper_status<>1"
    )]

    incidents: list[dict[str, Any]] = []
    for device in offline:
        observed: list[dict[str, Any]] = [{
            "type": "device_status",
            "device_id": device["device_id"],
            "fact": "offline",
            "last_poll": device["last_poll"],
            "last_success": device["last_success"],
        }]
        related_events = [e for e in events if e.get("device_id") == device["device_id"]]
        for event in related_events[-10:]:
            observed.append({
                "type": "snmp_event", "event_id": event["event_id"], "ts": event["ts"],
                "trap_oid": event["trap_oid"], "event_type": event["event_type"],
                "severity": event["severity"],
            })

        upstream_candidates: list[dict[str, Any]] = []
        for link in links:
            if link.get("remote_device_id") == device["device_id"]:
                local_down = [i for i in interfaces if i["device_id"] == link["local_device_id"] and i["if_index"] == link["local_if_index"]]
                if local_down:
                    upstream_candidates.append({
                        "link_id": link["link_id"],
                        "upstream_device_id": link["local_device_id"],
                        "local_if_index": link["local_if_index"],
                        "confidence": link["confidence"],
                        "evidence_type": link["evidence_type"],
                        "interface": local_down[0],
                    })

        inference = None
        confidence = "low"
        recommendation = "Repoll the device and inspect authentication, reachability, and adjacent-link evidence."
        confirmed = [x for x in upstream_candidates if x["confidence"] == "confirmed"]
        if confirmed:
            candidate = confirmed[0]
            inference = (
                f"A confirmed topology link on upstream device {candidate['upstream_device_id']} "
                f"has an administratively-up but operationally-down interface and may be a common cause."
            )
            confidence = "high" if related_events else "medium"
            recommendation = "Inspect the confirmed upstream interface and its peer before changing device configuration."
            observed.append({"type": "confirmed_topology_link", **candidate})
        elif upstream_candidates:
            candidate = upstream_candidates[0]
            inference = "An inferred topology relationship overlaps a down interface; treat it as a hypothesis, not a verified cause."
            confidence = "low"
            recommendation = "Verify the inferred topology link before acting on it."
            observed.append({"type": "inferred_topology_link", **candidate})

        incidents.append({
            "incident_id": str(uuid.uuid4()),
            "subject_device_id": device["device_id"],
            "observed_facts": observed,
            "derived_metrics": {"related_event_count": len(related_events)},
            "deterministic_rule_result": "correlated" if upstream_candidates else "no_common_cause_proven",
            "ai_inference": inference,
            "confidence": confidence,
            "recommended_action": recommendation,
            "executed_action": None,
        })

    return incidents


def incident_summary(conn, *, minutes: int = 15) -> dict[str, Any]:
    incidents = correlate_recent(conn, minutes=minutes)
    return {
        "window_minutes": minutes,
        "incident_count": len(incidents),
        "incidents": incidents,
        "method": "deterministic-correlation",
        "note": "AI may interpret this evidence, but deterministic observations and topology confidence remain authoritative.",
    }


def main() -> int:
    import argparse
    from edge1_snmp_platform import connect_db
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=int, default=15)
    args = parser.parse_args()
    with connect_db() as conn:
        print(json.dumps(incident_summary(conn, minutes=args.minutes), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
