#!/usr/bin/env python3
"""Publish sanitized Security Operations telemetry with bounded fallback caching."""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any, Iterable

SOURCE = Path("/var/lib/bigbird/operations-center/latest.json")
OUTPUT = Path("/var/www/edge1-status/security-operations.json")
MAX_ALERTS = 50
CACHE_WARNING = "Live collector refresh failed; displaying the last known good sanitized snapshot."
GENERIC_TITLES = {
    "unclassified suricata alert",
    "unknown ids signature",
    "unknown signature",
    "suricata alert",
}


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def parse_timestamp(value: Any) -> datetime.datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def cache_age_seconds(generated_at: Any) -> int | None:
    generated = parse_timestamp(generated_at)
    if generated is None:
        return None
    return max(0, int((datetime.datetime.now(datetime.timezone.utc) - generated).total_seconds()))


def safe_text(value: Any, limit: int = 500) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\x00", "").strip()
    return text[:limit] or None


def first_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def nested_value(document: dict[str, Any], path: str) -> Any:
    value: Any = document
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def first_path(document: dict[str, Any], paths: Iterable[str]) -> Any:
    return first_value(*(nested_value(document, path) for path in paths))


def safe_int(value: Any, minimum: int = 0, maximum: int | None = None) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < minimum or (maximum is not None and number > maximum):
        return None
    return number


def safe_identifier(value: Any) -> int | str | None:
    number = safe_int(value)
    if number is not None:
        return number
    return safe_text(value, 120)


def normalize_explicit_risk(value: Any) -> str:
    text = safe_text(value, 40)
    if not text:
        return "unknown"
    normalized = text.lower()
    if normalized in {"critical", "severe"}:
        return "critical"
    if normalized in {"high", "major"}:
        return "high"
    if normalized in {"medium", "moderate", "warning"}:
        return "medium"
    if normalized in {"low", "minor"}:
        return "low"
    if normalized in {"info", "informational", "notice"}:
        return "info"
    return "unknown"


def suricata_severity_risk(value: Any) -> str:
    """Map Suricata EVE severity where lower numbers are more important."""
    severity = safe_int(value)
    if severity is None:
        return "unknown"
    if severity <= 0:
        return "critical"
    if severity == 1:
        return "high"
    if severity == 2:
        return "medium"
    if severity == 3:
        return "low"
    return "info"


def meaningful_title(value: Any) -> str | None:
    title = safe_text(value, 300)
    if not title or title.lower() in GENERIC_TITLES:
        return None
    return title


def sanitize_alert(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    explanation = raw.get("explanation") if isinstance(raw.get("explanation"), dict) else {}
    embedded = raw.get("alert") if isinstance(raw.get("alert"), dict) else {}

    signature = meaningful_title(first_value(raw.get("signature"), embedded.get("signature")))
    explanation_title = safe_text(explanation.get("title"), 300)
    title = signature or explanation_title or "Unclassified Suricata alert"

    severity = safe_int(first_value(
        raw.get("suricata_severity"),
        embedded.get("severity"),
        raw.get("severity") if isinstance(raw.get("severity"), (int, float)) else None,
    ))
    risk = normalize_explicit_risk(first_value(raw.get("risk"), explanation.get("risk")))
    if risk == "unknown":
        risk = suricata_severity_risk(severity)

    category = safe_text(first_value(raw.get("category"), embedded.get("category")), 200)
    action = safe_text(first_value(raw.get("action"), embedded.get("action")), 80)
    protocol = safe_text(first_value(raw.get("protocol"), raw.get("proto")), 40)
    app_protocol = safe_text(first_value(
        raw.get("app_protocol"), raw.get("app_proto"), raw.get("application_protocol")
    ), 80)

    source = safe_text(first_value(raw.get("source"), raw.get("src_ip"), raw.get("source_ip")), 255)
    destination = safe_text(first_value(
        raw.get("destination"), raw.get("dest_ip"), raw.get("destination_ip")
    ), 255)
    source_port = safe_int(first_value(raw.get("source_port"), raw.get("src_port")), 1, 65535)
    destination_port = safe_int(first_value(
        raw.get("destination_port"), raw.get("dest_port"), raw.get("dst_port")
    ), 1, 65535)

    signature_id = safe_int(first_value(raw.get("signature_id"), raw.get("sid"), embedded.get("signature_id")))
    generator_id = safe_int(first_value(raw.get("generator_id"), raw.get("gid"), embedded.get("gid")))
    revision = safe_int(first_value(raw.get("revision"), raw.get("rev"), embedded.get("rev")))
    flow_id = safe_identifier(first_value(raw.get("flow_id"), raw.get("event_id")))
    timestamp = safe_text(first_value(
        raw.get("timestamp"), raw.get("event_time"), raw.get("time"), raw.get("created_at")
    ), 100)

    existing_meaning = safe_text(explanation.get("meaning"), 700)
    if signature and (not existing_meaning or existing_meaning == "Suricata detected a rule match."):
        category_phrase = f' in category "{category}"' if category else ""
        meaning = f'Suricata matched the rule "{signature}"{category_phrase}.'
    else:
        meaning = existing_meaning or "Suricata detected a rule match."

    recommendation = safe_text(explanation.get("recommendation"), 700)
    if not recommendation or recommendation == "Review source and rule details.":
        recommendation = (
            "Review the endpoints, ports, application protocol, rule identifiers, and related telemetry "
            "to determine whether the observed connection is expected."
        )

    return {
        "timestamp": timestamp,
        "signature": signature or title,
        "risk": risk,
        "suricata_severity": severity,
        "source": source,
        "source_port": source_port,
        "destination": destination,
        "destination_port": destination_port,
        "protocol": protocol,
        "app_protocol": app_protocol,
        "category": category,
        "action": action,
        "signature_id": signature_id,
        "gid": generator_id,
        "rev": revision,
        "flow_id": flow_id,
        "explanation": {
            "title": signature or title,
            "risk": risk,
            "meaning": meaning,
            "recommendation": recommendation,
        },
        "normalization": {
            "schema": "wwcx.suricata-alert.v1",
            "sanitized": True,
            "packet_payload_included": False,
            "raw_event_included": False,
        },
    }


def sanitize_alerts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    alerts: list[dict[str, Any]] = []
    for raw in value[:MAX_ALERTS]:
        sanitized = sanitize_alert(raw)
        if sanitized is not None:
            alerts.append(sanitized)
    return alerts


def load_existing_snapshot() -> dict[str, Any] | None:
    try:
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("available") is not True:
        return None
    return data


def evidence_records() -> list[dict[str, str]]:
    evidence_dir = Path("/var/lib/edge1-operations-api/evidence/security")
    records: list[dict[str, str]] = []
    if not evidence_dir.exists():
        return records
    for item in sorted(evidence_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)[:5]:
        records.append({
            "file": item.name,
            "modified": datetime.datetime.fromtimestamp(
                item.stat().st_mtime,
                datetime.timezone.utc,
            ).isoformat(),
        })
    return records


def live_snapshot() -> dict[str, Any]:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("operations-center source is not an object")
    security = raw.get("security", {})
    if not isinstance(security, dict):
        security = {}
    generated_at = raw.get("generated_at") or utc_now()
    alerts = sanitize_alerts(security.get("recent_alerts", []))
    return {
        "schema_version": "2.0",
        "generated_at": generated_at,
        "available": bool(security.get("available", False)),
        "engine": security.get("engine", {}),
        "logs": security.get("logs", {}),
        "health": security.get("health", {}),
        "counts": security.get("counts", {}),
        "recent_alerts": alerts,
        "normalization": {
            "alert_schema": "wwcx.suricata-alert.v1",
            "alert_limit": MAX_ALERTS,
            "sanitized": True,
            "raw_events_included": False,
            "packet_payloads_included": False,
        },
        "evidence": evidence_records(),
        "advisories": [
            "Runtime configuration override detected: wwcx-runtime.yaml defines the active af-packet sensor interface (wg0). This is expected BigBird deployment behavior."
        ],
        "cache": {
            "mode": "live",
            "stale": False,
            "snapshot_generated_at": generated_at,
            "age_seconds": cache_age_seconds(generated_at),
            "source_error": None,
        },
    }


def fallback_snapshot(error: Exception) -> dict[str, Any]:
    cached = load_existing_snapshot()
    if cached is None:
        return {
            "schema_version": "2.0",
            "generated_at": utc_now(),
            "available": False,
            "error": str(error),
            "engine": {},
            "logs": {},
            "health": {"status": "error", "warnings": [str(error)]},
            "counts": {},
            "recent_alerts": [],
            "normalization": {
                "alert_schema": "wwcx.suricata-alert.v1",
                "alert_limit": MAX_ALERTS,
                "sanitized": True,
                "raw_events_included": False,
                "packet_payloads_included": False,
            },
            "cache": {
                "mode": "unavailable",
                "stale": True,
                "snapshot_generated_at": None,
                "age_seconds": None,
                "source_error": str(error),
            },
        }

    snapshot_generated_at = cached.get("generated_at")
    cached["cache"] = {
        "mode": "last_known_good",
        "stale": True,
        "snapshot_generated_at": snapshot_generated_at,
        "age_seconds": cache_age_seconds(snapshot_generated_at),
        "source_error": str(error),
    }
    cached.setdefault("health", {})
    warnings = cached["health"].get("warnings", [])
    if not isinstance(warnings, list):
        warnings = []
    warnings = [item for item in warnings if item != CACHE_WARNING]
    cached["health"]["warnings"] = warnings + [CACHE_WARNING]
    cached["error"] = str(error)
    return cached


def write_snapshot(data: dict[str, Any]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o644)
    temporary.replace(OUTPUT)


def main() -> None:
    try:
        data = live_snapshot()
    except Exception as exc:  # bounded fallback must cover source and parsing errors
        data = fallback_snapshot(exc)
    write_snapshot(data)
    print(json.dumps({
        "ok": True,
        "output": str(OUTPUT),
        "cache_mode": (data.get("cache") or {}).get("mode"),
        "alert_count": len(data.get("recent_alerts") or []),
        "schema_version": data.get("schema_version"),
    }))


if __name__ == "__main__":
    main()
