#!/usr/bin/env python3
"""Build a read-only, privacy-preserving Edge1 security correlation snapshot."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import ipaddress
import json
import os
from pathlib import Path
from typing import Any, Iterable

DEFAULT_SECURITY = Path("/var/www/edge1-status/security-operations.json")
DEFAULT_NETWORK = Path("/var/www/edge1-status/operations-network.json")
DEFAULT_OPERATIONS = Path("/var/lib/bigbird/operations-center/latest.json")
DEFAULT_SPAMHAUS = Path("/var/lib/bigbird-networking/spamhaus/summary.txt")
DEFAULT_OUTPUT = Path("/var/www/edge1-status/security-correlation.json")
DEFAULT_WINDOW_SECONDS = 300
MAX_EVENTS = 500

CATEGORY_KEYS = {
    "dns": ("recent_dns_queries", "dns_queries", "dns_events", "queries"),
    "firewall": ("recent_firewall_events", "firewall_events", "nftables_events", "drops"),
    "fail2ban": ("recent_fail2ban_events", "fail2ban_events", "bans"),
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_timestamp(value: Any) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return dt.datetime.fromtimestamp(float(value), dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def iso_timestamp(value: Any) -> str | None:
    parsed = parse_timestamp(value)
    return parsed.isoformat() if parsed else None


def safe_text(value: Any, limit: int = 500) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:limit]


def load_json(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, f"missing source: {path}"
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"unreadable source {path}: {exc}"
    if not isinstance(data, dict):
        return {}, f"invalid source document: {path}"
    return data, None


def parse_spamhaus_summary(path: Path) -> tuple[dict[str, int], str | None]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {}, f"missing source: {path}"
    except OSError as exc:
        return {}, f"unreadable source {path}: {exc}"
    values: dict[str, int] = {}
    for line in lines:
        key, separator, raw_value = line.partition("=")
        if not separator:
            continue
        key = key.strip()
        if key not in {"drop4", "edrop4", "combined4", "drop6"}:
            continue
        try:
            values[key] = int(raw_value.strip())
        except ValueError:
            continue
    return values, None if values else f"no recognized Spamhaus counts in {path}"


def normalize_risk(value: Any) -> str:
    if isinstance(value, (int, float)):
        number = int(value)
        if number >= 4:
            return "critical"
        if number == 3:
            return "high"
        if number == 2:
            return "medium"
        if number == 1:
            return "low"
    text = safe_text(value, 40).lower()
    if text in {"critical", "severe"}:
        return "critical"
    if text in {"high", "major"}:
        return "high"
    if text in {"medium", "moderate", "warning"}:
        return "medium"
    if text in {"low", "minor"}:
        return "low"
    if text in {"info", "informational", "notice"}:
        return "info"
    return "unknown"


def first_value(item: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def endpoint(value: Any) -> str | None:
    text = safe_text(value, 255)
    if not text:
        return None
    if text.startswith("[") and "]" in text:
        text = text[1:text.index("]")]
    elif text.count(":") == 1:
        host, port = text.rsplit(":", 1)
        if port.isdigit():
            text = host
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        return text.lower()


def domain_name(value: Any) -> str | None:
    text = safe_text(value, 253).strip(".").lower()
    return text or None


def event_id(category: str, timestamp: str | None, title: str, source: str | None, destination: str | None) -> str:
    material = "|".join([category, timestamp or "", title, source or "", destination or ""])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def normalize_ids_alerts(security: dict[str, Any]) -> list[dict[str, Any]]:
    alerts = security.get("recent_alerts", [])
    if not isinstance(alerts, list):
        return []
    normalized: list[dict[str, Any]] = []
    for raw in alerts[:200]:
        if not isinstance(raw, dict):
            continue
        explanation = raw.get("explanation") if isinstance(raw.get("explanation"), dict) else {}
        embedded = raw.get("alert") if isinstance(raw.get("alert"), dict) else {}
        timestamp = iso_timestamp(first_value(raw, ("timestamp", "event_time", "time", "created_at")))
        title = safe_text(first_value(explanation, ("title",)) or first_value(raw, ("signature",)) or embedded.get("signature") or "Unknown IDS signature", 300)
        source = endpoint(first_value(raw, ("source", "src_ip", "source_ip")))
        destination = endpoint(first_value(raw, ("destination", "dest_ip", "destination_ip")))
        domain = domain_name(first_value(raw, ("domain", "hostname", "rrname", "query")))
        risk = normalize_risk(first_value(explanation, ("risk",)) or first_value(raw, ("risk", "severity")))
        normalized.append({
            "id": event_id("ids", timestamp, title, source, destination),
            "category": "ids",
            "timestamp": timestamp,
            "severity": risk,
            "title": title,
            "source": source,
            "destination": destination,
            "domain": domain,
            "detail": safe_text(explanation.get("meaning") or raw.get("category") or "Suricata IDS alert", 500),
            "recommendation": safe_text(explanation.get("recommendation") or "Review related DNS, firewall, and host activity.", 500),
        })
    return normalized


def find_event_lists(document: Any, candidate_keys: Iterable[str]) -> list[dict[str, Any]]:
    candidates = set(candidate_keys)
    results: list[dict[str, Any]] = []

    def walk(value: Any, depth: int) -> None:
        if depth > 5:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                if key in candidates and isinstance(child, list):
                    results.extend(item for item in child if isinstance(item, dict))
                elif isinstance(child, (dict, list)):
                    walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value[:200]:
                if isinstance(child, (dict, list)):
                    walk(child, depth + 1)

    walk(document, 0)
    return results[:300]


def normalize_generic_event(category: str, raw: dict[str, Any]) -> dict[str, Any]:
    timestamp = iso_timestamp(first_value(raw, ("timestamp", "time", "observed_at", "created_at", "event_time")))
    source = endpoint(first_value(raw, ("source", "src", "src_ip", "source_ip", "client", "client_ip", "address", "ip")))
    destination = endpoint(first_value(raw, ("destination", "dst", "dest_ip", "destination_ip", "server", "server_ip")))
    domain = domain_name(first_value(raw, ("domain", "hostname", "qname", "rrname", "query", "name")))
    action = safe_text(first_value(raw, ("action", "verdict", "decision", "state", "status")), 80)
    title = safe_text(first_value(raw, ("title", "signature", "reason", "message")) or f"{category.title()} event", 300)
    detail = safe_text(first_value(raw, ("detail", "message", "reason", "rule", "jail")) or action or title, 500)
    severity = normalize_risk(first_value(raw, ("severity", "risk", "priority")))
    if severity == "unknown" and action.lower() in {"drop", "blocked", "block", "ban", "banned", "reject"}:
        severity = "medium"
    return {
        "id": event_id(category, timestamp, title, source, destination),
        "category": category,
        "timestamp": timestamp,
        "severity": severity,
        "title": title,
        "source": source,
        "destination": destination,
        "domain": domain,
        "action": action or None,
        "detail": detail,
    }


def normalize_operations_events(operations: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for category, keys in CATEGORY_KEYS.items():
        for raw in find_event_lists(operations, keys):
            events.append(normalize_generic_event(category, raw))
    unique: dict[str, dict[str, Any]] = {item["id"]: item for item in events}
    return list(unique.values())


def identifiers(event: dict[str, Any]) -> set[str]:
    values = {event.get("source"), event.get("destination"), event.get("domain")}
    return {str(value).lower() for value in values if value and value != "unknown"}


def seconds_between(left: dict[str, Any], right: dict[str, Any]) -> float | None:
    left_time = parse_timestamp(left.get("timestamp"))
    right_time = parse_timestamp(right.get("timestamp"))
    if not left_time or not right_time:
        return None
    return abs((left_time - right_time).total_seconds())


def build_correlations(events: list[dict[str, Any]], window_seconds: int) -> list[dict[str, Any]]:
    anchors = [event for event in events if event.get("category") == "ids"]
    related_pool = [event for event in events if event.get("category") != "ids"]
    correlations: list[dict[str, Any]] = []
    for anchor in anchors:
        anchor_identifiers = identifiers(anchor)
        matches: list[dict[str, Any]] = []
        match_reasons: set[str] = set()
        categories: set[str] = set()
        for candidate in related_pool:
            delta = seconds_between(anchor, candidate)
            if delta is None or delta > window_seconds:
                continue
            overlap = sorted(anchor_identifiers.intersection(identifiers(candidate)))
            if not overlap:
                continue
            categories.add(str(candidate.get("category")))
            match_reasons.update(overlap)
            matches.append({
                "event_id": candidate["id"],
                "category": candidate.get("category"),
                "seconds_from_anchor": int(delta),
                "matched_identifiers": overlap,
            })
        if not matches:
            continue
        confidence = "high" if len(categories) >= 2 else "medium"
        matches.sort(key=lambda item: (item["seconds_from_anchor"], item["category"] or ""))
        correlations.append({
            "id": f"corr-{anchor['id']}",
            "anchor_event_id": anchor["id"],
            "confidence": confidence,
            "related_categories": sorted(categories),
            "matched_identifiers": sorted(match_reasons),
            "related_events": matches,
            "explanation": "Events share an endpoint or domain and occurred within the configured time window.",
            "caution": "This is an investigative lead and does not prove causation.",
        })
    return correlations


def source_record(path: Path, available: bool, detail: str) -> dict[str, Any]:
    modified = None
    try:
        modified = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat()
    except OSError:
        pass
    return {"path": str(path), "available": available, "modified_at": modified, "detail": detail}


def build_snapshot(
    security_path: Path = DEFAULT_SECURITY,
    network_path: Path = DEFAULT_NETWORK,
    operations_path: Path = DEFAULT_OPERATIONS,
    spamhaus_path: Path = DEFAULT_SPAMHAUS,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
) -> dict[str, Any]:
    warnings: list[str] = []
    security, security_error = load_json(security_path)
    network, network_error = load_json(network_path)
    operations, operations_error = load_json(operations_path)
    spamhaus, spamhaus_error = parse_spamhaus_summary(spamhaus_path)

    errors = {
        "security": security_error,
        "network": network_error,
        "operations": operations_error,
        "spamhaus": spamhaus_error,
    }
    warnings.extend(error for error in errors.values() if error)

    ids_events = normalize_ids_alerts(security)
    supporting_events = normalize_operations_events(operations)
    events = (ids_events + supporting_events)[:MAX_EVENTS]
    events.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
    correlations = build_correlations(events, max(1, int(window_seconds)))

    category_counts: dict[str, int] = {}
    for item in events:
        category = str(item.get("category") or "unknown")
        category_counts[category] = category_counts.get(category, 0) + 1

    source_status = {
        "security": source_record(security_path, security_error is None, security_error or "loaded"),
        "network": source_record(network_path, network_error is None, network_error or "loaded"),
        "operations": source_record(operations_path, operations_error is None, operations_error or "loaded"),
        "spamhaus": source_record(spamhaus_path, spamhaus_error is None, spamhaus_error or "loaded"),
    }

    return {
        "schema_version": "1.0",
        "generated_at": utc_now(),
        "read_only": True,
        "correlation_window_seconds": max(1, int(window_seconds)),
        "privacy": {
            "packet_payloads_included": False,
            "credentials_included": False,
            "private_keys_included": False,
            "raw_logs_included": False,
            "event_fields_minimized": True,
        },
        "source_status": source_status,
        "network_context": {
            "interface_count": len(network.get("interfaces", [])) if isinstance(network.get("interfaces"), list) else 0,
            "wireguard_available": bool(network.get("wireguard_available", False)),
            "resolver_observed": bool(network.get("resolver")),
        },
        "reputation_context": {
            "spamhaus": spamhaus,
            "configured_entries": int(spamhaus.get("combined4", 0)) + int(spamhaus.get("drop6", 0)),
        },
        "summary": {
            "event_count": len(events),
            "correlation_count": len(correlations),
            "high_confidence_count": sum(1 for item in correlations if item["confidence"] == "high"),
            "category_counts": category_counts,
            "available_source_count": sum(1 for item in source_status.values() if item["available"]),
            "source_count": len(source_status),
        },
        "events": events,
        "correlations": correlations,
        "warnings": warnings,
        "limitations": [
            "Only telemetry present in the configured snapshots can be correlated.",
            "Events without parseable timestamps cannot participate in time-window correlation.",
            "A correlation is an investigative lead and does not prove causation.",
        ],
    }


def write_snapshot(snapshot: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o644)
    temporary.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--security", type=Path, default=DEFAULT_SECURITY)
    parser.add_argument("--network", type=Path, default=DEFAULT_NETWORK)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--spamhaus", type=Path, default=DEFAULT_SPAMHAUS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--window-seconds", type=int, default=DEFAULT_WINDOW_SECONDS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = build_snapshot(
        security_path=args.security,
        network_path=args.network,
        operations_path=args.operations,
        spamhaus_path=args.spamhaus,
        window_seconds=args.window_seconds,
    )
    write_snapshot(snapshot, args.output)
    print(json.dumps({"ok": True, "output": str(args.output), "events": snapshot["summary"]["event_count"], "correlations": snapshot["summary"]["correlation_count"]}))


if __name__ == "__main__":
    main()
