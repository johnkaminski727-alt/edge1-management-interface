#!/usr/bin/env python3
"""Extend Security Correlation with optional Edge1 network-sensor events."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import security_correlation_exporter as base

DEFAULT_SENSOR = Path("/var/lib/wwcx-network-sensor/restricted/latest.json")
MAX_SENSOR_EVENTS = 300


def nested(document: dict[str, Any], key: str) -> dict[str, Any]:
    value = document.get(key)
    return value if isinstance(value, dict) else {}


def sensor_domain(event: dict[str, Any]) -> str | None:
    dns = nested(event, "dns")
    http = nested(event, "http")
    tls = nested(event, "tls")
    return base.domain_name(
        base.first_value(dns, ("rrname", "query"))
        or base.first_value(http, ("hostname", "host"))
        or base.first_value(tls, ("sni", "server_name"))
        or base.first_value(event, ("query", "host", "server_name"))
    )


def normalize_suricata_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    event_type = base.safe_text(raw.get("event_type"), 40).lower()
    if not event_type:
        return None
    alert = nested(raw, "alert")
    source = base.endpoint(base.first_value(raw, ("src_ip", "source", "source_ip")))
    destination = base.endpoint(base.first_value(raw, ("dest_ip", "destination", "destination_ip")))
    domain = sensor_domain(raw)
    timestamp = base.iso_timestamp(base.first_value(raw, ("timestamp", "event_time", "time")))

    if event_type == "alert":
        category = "ids"
        title = base.safe_text(alert.get("signature") or "Network sensor IDS alert", 300)
        severity = base.normalize_risk(alert.get("severity") or raw.get("severity"))
        detail = base.safe_text(alert.get("category") or "Suricata alert observed on the mirrored network link.", 500)
    elif event_type == "dns":
        category = "dns"
        title = base.safe_text(f"Network sensor DNS query{': ' + domain if domain else ''}", 300)
        severity = "info"
        detail = "DNS activity observed on the mirrored network link."
    else:
        category = "network"
        app_proto = base.safe_text(raw.get("app_proto"), 64)
        protocol = base.safe_text(raw.get("proto"), 32)
        title = base.safe_text(f"Network sensor {event_type} event", 300)
        severity = "info"
        details = [value for value in (protocol, app_proto) if value]
        detail = base.safe_text(" / ".join(details) or "Network activity observed on the mirrored link.", 500)

    return {
        "id": base.event_id(category, timestamp, title, source, destination),
        "category": category,
        "timestamp": timestamp,
        "severity": severity,
        "title": title,
        "source": source,
        "destination": destination,
        "domain": domain,
        "detail": detail,
        "recommendation": "Review the restricted network-sensor snapshot and retained PCAP when investigation is required.",
        "sensor": "edge1-passive",
    }


def normalize_zeek_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    log_name = base.safe_text(raw.get("zeek_log"), 40).lower()
    if not log_name:
        return None
    source = base.endpoint(base.first_value(raw, ("id.orig_h", "src_ip", "source")))
    destination = base.endpoint(base.first_value(raw, ("id.resp_h", "dest_ip", "destination")))
    domain = base.domain_name(base.first_value(raw, ("query", "host", "server_name")))
    timestamp = base.iso_timestamp(base.first_value(raw, ("ts", "timestamp", "time")))
    category = "dns" if log_name == "dns" else "network"
    title = base.safe_text(
        f"Network sensor Zeek {log_name}{': ' + domain if domain and log_name in {'dns', 'http', 'ssl'} else ''}",
        300,
    )
    return {
        "id": base.event_id(category, timestamp, title, source, destination),
        "category": category,
        "timestamp": timestamp,
        "severity": "info",
        "title": title,
        "source": source,
        "destination": destination,
        "domain": domain,
        "detail": base.safe_text(f"Zeek {log_name} metadata observed on the mirrored network link.", 500),
        "recommendation": "Review the restricted Zeek record and retained PCAP when investigation is required.",
        "sensor": "edge1-passive",
    }


def normalize_sensor_events(sensor: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    suricata = sensor.get("recent_suricata_events")
    if isinstance(suricata, list):
        for raw in suricata[-MAX_SENSOR_EVENTS:]:
            if isinstance(raw, dict):
                event = normalize_suricata_event(raw)
                if event:
                    normalized.append(event)
    zeek = sensor.get("recent_zeek_events")
    if isinstance(zeek, list):
        for raw in zeek[-MAX_SENSOR_EVENTS:]:
            if isinstance(raw, dict):
                event = normalize_zeek_event(raw)
                if event:
                    normalized.append(event)
    unique = {event["id"]: event for event in normalized}
    return list(unique.values())[-MAX_SENSOR_EVENTS:]


def validate_sensor(sensor: dict[str, Any]) -> str | None:
    if sensor.get("contract") != "wwcx.edge1-network-sensor.v1":
        return "network sensor contract is unsupported"
    if sensor.get("visibility") != "restricted-owner-full":
        return "network sensor restricted snapshot is required"
    return None


def augment_snapshot(snapshot: dict[str, Any], sensor: dict[str, Any], sensor_path: Path) -> dict[str, Any]:
    error = validate_sensor(sensor)
    if error:
        snapshot.setdefault("warnings", []).append(error)
        return snapshot

    sensor_events = normalize_sensor_events(sensor)
    combined = list(snapshot.get("events", [])) + sensor_events
    unique = {event["id"]: event for event in combined if isinstance(event, dict) and event.get("id")}
    events = list(unique.values())
    events.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
    events = events[:base.MAX_EVENTS]
    correlations = base.build_correlations(events, int(snapshot.get("correlation_window_seconds", base.DEFAULT_WINDOW_SECONDS)))

    category_counts: dict[str, int] = {}
    for event in events:
        category = str(event.get("category") or "unknown")
        category_counts[category] = category_counts.get(category, 0) + 1

    source_status = snapshot.setdefault("source_status", {})
    source_status["network_sensor"] = base.source_record(sensor_path, True, "loaded")
    summary = snapshot.setdefault("summary", {})
    summary.update({
        "event_count": len(events),
        "correlation_count": len(correlations),
        "high_confidence_count": sum(1 for item in correlations if item.get("confidence") == "high"),
        "category_counts": category_counts,
        "available_source_count": sum(1 for item in source_status.values() if item.get("available")),
        "source_count": len(source_status),
        "network_sensor_event_count": len(sensor_events),
    })
    snapshot["events"] = events
    snapshot["correlations"] = correlations
    snapshot["network_sensor_context"] = {
        "contract": sensor.get("contract"),
        "profile": sensor.get("profile"),
        "mode": sensor.get("mode"),
        "interface": sensor.get("interface"),
        "events_normalized": len(sensor_events),
        "restricted_payloads_copied": False,
    }
    return snapshot


def build_snapshot(
    security_path: Path = base.DEFAULT_SECURITY,
    network_path: Path = base.DEFAULT_NETWORK,
    operations_path: Path = base.DEFAULT_OPERATIONS,
    spamhaus_path: Path = base.DEFAULT_SPAMHAUS,
    sensor_path: Path = DEFAULT_SENSOR,
    window_seconds: int = base.DEFAULT_WINDOW_SECONDS,
) -> dict[str, Any]:
    snapshot = base.build_snapshot(
        security_path=security_path,
        network_path=network_path,
        operations_path=operations_path,
        spamhaus_path=spamhaus_path,
        window_seconds=window_seconds,
    )
    if not sensor_path.is_file():
        return snapshot
    sensor, error = base.load_json(sensor_path)
    if error:
        snapshot.setdefault("warnings", []).append(error)
        return snapshot
    return augment_snapshot(snapshot, sensor, sensor_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--security", type=Path, default=base.DEFAULT_SECURITY)
    parser.add_argument("--network", type=Path, default=base.DEFAULT_NETWORK)
    parser.add_argument("--operations", type=Path, default=base.DEFAULT_OPERATIONS)
    parser.add_argument("--spamhaus", type=Path, default=base.DEFAULT_SPAMHAUS)
    parser.add_argument("--sensor", type=Path, default=DEFAULT_SENSOR)
    parser.add_argument("--output", type=Path, default=base.DEFAULT_OUTPUT)
    parser.add_argument("--window-seconds", type=int, default=base.DEFAULT_WINDOW_SECONDS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = build_snapshot(
        security_path=args.security,
        network_path=args.network,
        operations_path=args.operations,
        spamhaus_path=args.spamhaus,
        sensor_path=args.sensor,
        window_seconds=args.window_seconds,
    )
    base.write_snapshot(snapshot, args.output)
    print({"ok": True, "output": str(args.output), "events": snapshot["summary"]["event_count"], "correlations": snapshot["summary"]["correlation_count"]})


if __name__ == "__main__":
    main()
