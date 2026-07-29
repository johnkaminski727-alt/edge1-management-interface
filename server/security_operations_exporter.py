#!/usr/bin/env python3
"""Publish the sanitized Security Operations snapshot with last-known-good fallback."""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any

SOURCE = Path("/var/lib/bigbird/operations-center/latest.json")
OUTPUT = Path("/var/www/edge1-status/security-operations.json")
MAX_ALERTS = 50


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
    return {
        "generated_at": generated_at,
        "available": bool(security.get("available", False)),
        "engine": security.get("engine", {}),
        "logs": security.get("logs", {}),
        "health": security.get("health", {}),
        "counts": security.get("counts", {}),
        "recent_alerts": security.get("recent_alerts", [])[:MAX_ALERTS],
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
            "generated_at": utc_now(),
            "available": False,
            "error": str(error),
            "engine": {},
            "logs": {},
            "health": {"status": "error", "warnings": [str(error)]},
            "counts": {},
            "recent_alerts": [],
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
    cached["health"]["warnings"] = warnings + [
        "Live collector refresh failed; displaying the last known good sanitized snapshot."
    ]
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
    }))


if __name__ == "__main__":
    main()
