#!/usr/bin/env python3
"""Build a minimized Edge1 public-status document from detailed local snapshots.

This repository-phase exporter has no live publication default. Inputs must be
provided explicitly and the default output remains under the repository build
folder. The output schema is an allowlist and never passes source objects,
strings, identifiers, paths, errors, or nested records through.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "wwcx.edge1-public-status.v1"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "build" / "edge1-public-status" / "status.json"
FRESH_SECONDS = 5 * 60
AGING_SECONDS = 15 * 60
MAX_PUBLIC_COUNT = 999
MAX_NOTICE_LENGTH = 160
COMPONENT_ORDER = ("security", "network_defense", "operations")
PUBLIC_TOP_LEVEL_FIELDS = {
    "schema_version",
    "generated_at",
    "overall_state",
    "component_category",
    "maintenance_notice",
    "read_only",
    "traffic_controls_changed",
}
PUBLIC_COMPONENT_FIELDS = {
    "component_category",
    "component_state",
    "bounded_count",
    "freshness_bucket",
}


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat()


def load_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


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


def freshness_bucket(document: dict[str, Any] | None, now: dt.datetime) -> str:
    if document is None:
        return "unknown"
    generated = parse_time(document.get("generated_at"))
    if generated is None:
        return "unknown"
    age = max(0.0, (now - generated).total_seconds())
    if age <= FRESH_SECONDS:
        return "fresh"
    if age <= AGING_SECONDS:
        return "aging"
    return "stale"


def bounded_count(value: Any, maximum: int = MAX_PUBLIC_COUNT) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return min(max(0, number), maximum)


def list_count(value: Any, maximum: int = MAX_PUBLIC_COUNT) -> int:
    return min(len(value), maximum) if isinstance(value, list) else 0


def normalize_state(value: Any, mapping: dict[str, str]) -> str:
    key = str(value or "").strip().lower()
    return mapping.get(key, "unavailable")


def component_record(
    category: str,
    state: str,
    count: int,
    freshness: str,
) -> dict[str, Any]:
    if category not in COMPONENT_ORDER:
        raise ValueError(f"Unsupported public component category: {category}")
    if state not in {"healthy", "limited", "attention", "unavailable"}:
        state = "unavailable"
    if freshness not in {"fresh", "aging", "stale", "unknown"}:
        freshness = "unknown"
    if freshness == "stale" and state != "unavailable":
        state = "attention"
    return {
        "component_category": category,
        "component_state": state,
        "bounded_count": bounded_count(count),
        "freshness_bucket": freshness,
    }


def security_component(document: dict[str, Any] | None, now: dt.datetime) -> dict[str, Any]:
    if document is None:
        return component_record("security", "unavailable", 0, "unknown")
    health = document.get("health") if isinstance(document.get("health"), dict) else {}
    state = normalize_state(
        health.get("status"),
        {
            "healthy": "healthy",
            "ok": "healthy",
            "limited": "limited",
            "warning": "attention",
            "degraded": "attention",
            "critical": "attention",
        },
    )
    return component_record(
        "security",
        state,
        list_count(document.get("recent_alerts")),
        freshness_bucket(document, now),
    )


def network_component(document: dict[str, Any] | None, now: dt.datetime) -> dict[str, Any]:
    if document is None:
        return component_record("network_defense", "unavailable", 0, "unknown")
    summary = document.get("summary") if isinstance(document.get("summary"), dict) else {}
    state = normalize_state(
        document.get("overall_state"),
        {
            "observed": "healthy",
            "healthy": "healthy",
            "limited": "limited",
            "stale": "attention",
            "attention": "attention",
            "unavailable": "unavailable",
        },
    )
    return component_record(
        "network_defense",
        state,
        bounded_count(summary.get("available_source_count"), 99),
        freshness_bucket(document, now),
    )


def operations_component(document: dict[str, Any] | None, now: dt.datetime) -> dict[str, Any]:
    if document is None:
        return component_record("operations", "unavailable", 0, "unknown")
    state = normalize_state(
        document.get("overall"),
        {
            "healthy": "healthy",
            "operational": "healthy",
            "limited": "limited",
            "attention": "attention",
            "warning": "attention",
            "critical": "attention",
        },
    )
    return component_record(
        "operations",
        state,
        list_count(document.get("checks"), 99),
        freshness_bucket(document, now),
    )


def overall_state(components: list[dict[str, Any]]) -> str:
    states = [str(item.get("component_state")) for item in components]
    if states and all(state == "unavailable" for state in states):
        return "unavailable"
    if "attention" in states:
        return "attention"
    if "limited" in states or "unavailable" in states:
        return "limited"
    return "healthy"


def sanitize_notice(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:MAX_NOTICE_LENGTH]


def assert_public_shape(document: dict[str, Any]) -> None:
    if set(document) != PUBLIC_TOP_LEVEL_FIELDS:
        raise ValueError("Public status top-level fields do not match the allowlist")
    components = document.get("component_category")
    if not isinstance(components, list) or len(components) != len(COMPONENT_ORDER):
        raise ValueError("Public status component set is incomplete")
    categories: list[str] = []
    for component in components:
        if not isinstance(component, dict) or set(component) != PUBLIC_COMPONENT_FIELDS:
            raise ValueError("Public component fields do not match the allowlist")
        categories.append(str(component.get("component_category")))
    if tuple(categories) != COMPONENT_ORDER:
        raise ValueError("Public component order or categories are invalid")
    if document.get("read_only") is not True:
        raise ValueError("Public status must remain read-only")
    if document.get("traffic_controls_changed") is not False:
        raise ValueError("Public status must not claim traffic-control changes")


def build_public_status(
    security_document: dict[str, Any] | None,
    network_document: dict[str, Any] | None,
    operations_document: dict[str, Any] | None,
    *,
    now: dt.datetime | None = None,
    maintenance_notice: str = "",
) -> dict[str, Any]:
    current = (now or utc_now()).astimezone(dt.timezone.utc)
    components = [
        security_component(security_document, current),
        network_component(network_document, current),
        operations_component(operations_document, current),
    ]
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso(current),
        "overall_state": overall_state(components),
        "component_category": components,
        "maintenance_notice": sanitize_notice(maintenance_notice),
        "read_only": True,
        "traffic_controls_changed": False,
    }
    assert_public_shape(result)
    return result


def write_public_status(document: dict[str, Any], output: Path) -> None:
    assert_public_shape(document)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o644)
    temporary.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--security", type=Path, required=True)
    parser.add_argument("--network-defense", type=Path, required=True)
    parser.add_argument("--operations-health", type=Path, required=True)
    parser.add_argument("--maintenance-notice", default="")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    document = build_public_status(
        load_object(args.security),
        load_object(args.network_defense),
        load_object(args.operations_health),
        maintenance_notice=args.maintenance_notice,
    )
    write_public_status(document, args.output)
    print(json.dumps({"ok": True, "output": str(args.output), "overall_state": document["overall_state"]}))


if __name__ == "__main__":
    main()
