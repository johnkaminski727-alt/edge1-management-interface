#!/usr/bin/env python3
"""Validate live Security Correlation and Network Defense acceptance evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

DEFAULT_MAX_AGE_SECONDS = 600
MAX_FUTURE_SKEW_SECONDS = 60


class AcceptanceError(ValueError):
    """Raised when an observability acceptance contract is not satisfied."""


def parse_timestamp(value: Any) -> dt.datetime:
    text = str(value or "").strip()
    if not text:
        raise AcceptanceError("generated_at is missing")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise AcceptanceError("generated_at is invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def load_document(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AcceptanceError(f"{label} document is missing") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise AcceptanceError(f"{label} document is unreadable") from exc
    if not isinstance(value, dict):
        raise AcceptanceError(f"{label} document is not an object")
    return value


def age_seconds(document: dict[str, Any], now: dt.datetime, label: str) -> int:
    generated = parse_timestamp(document.get("generated_at"))
    delta = (now - generated).total_seconds()
    if delta < -MAX_FUTURE_SKEW_SECONDS:
        raise AcceptanceError(f"{label} generated_at is too far in the future")
    return max(0, int(delta))


def require_false(mapping: dict[str, Any], keys: tuple[str, ...], prefix: str) -> None:
    for key in keys:
        if mapping.get(key) is not False:
            raise AcceptanceError(f"{prefix}.{key} must be false")


def validate_correlation(document: dict[str, Any], now: dt.datetime, max_age_seconds: int) -> dict[str, Any]:
    if document.get("read_only") is not True:
        raise AcceptanceError("correlation.read_only must be true")
    privacy = document.get("privacy")
    if not isinstance(privacy, dict):
        raise AcceptanceError("correlation.privacy contract is missing")
    require_false(
        privacy,
        ("packet_payloads_included", "credentials_included", "private_keys_included", "raw_logs_included"),
        "correlation.privacy",
    )
    if privacy.get("event_fields_minimized") is not True:
        raise AcceptanceError("correlation.privacy.event_fields_minimized must be true")
    summary = document.get("summary")
    if not isinstance(summary, dict):
        raise AcceptanceError("correlation.summary contract is missing")
    age = age_seconds(document, now, "correlation")
    if age > max_age_seconds:
        raise AcceptanceError(f"correlation snapshot is stale: {age}s")
    return {
        "age_seconds": age,
        "events": summary.get("event_count"),
        "correlations": summary.get("correlation_count"),
        "available_sources": summary.get("available_source_count"),
        "source_count": summary.get("source_count"),
    }


def validate_network_defense(document: dict[str, Any], now: dt.datetime, max_age_seconds: int) -> dict[str, Any]:
    if document.get("read_only") is not True:
        raise AcceptanceError("network_defense.read_only must be true")
    if document.get("traffic_controls_changed") is not False:
        raise AcceptanceError("network_defense.traffic_controls_changed must be false")
    dns = document.get("dns_policy")
    if not isinstance(dns, dict):
        raise AcceptanceError("network_defense.dns_policy contract is missing")
    require_false(
        dns,
        ("enforcement_enabled", "enforcement_verified", "traffic_controls_changed"),
        "network_defense.dns_policy",
    )
    if dns.get("requires_explicit_activation") is not True:
        raise AcceptanceError("network_defense.dns_policy.requires_explicit_activation must be true")
    sources = document.get("sources")
    if not isinstance(sources, dict):
        raise AcceptanceError("network_defense.sources contract is missing")
    correlation = sources.get("correlation")
    if not isinstance(correlation, dict):
        raise AcceptanceError("network_defense.sources.correlation is missing")
    if correlation.get("available") is not True:
        raise AcceptanceError("Network Defense has not consumed Security Correlation yet")
    if correlation.get("stale") is True:
        raise AcceptanceError("Network Defense reports Security Correlation as stale")
    age = age_seconds(document, now, "network_defense")
    if age > max_age_seconds:
        raise AcceptanceError(f"Network Defense snapshot is stale: {age}s")
    summary = document.get("summary") if isinstance(document.get("summary"), dict) else {}
    return {
        "age_seconds": age,
        "overall_state": document.get("overall_state"),
        "available_sources": summary.get("available_source_count"),
        "source_count": summary.get("source_count"),
        "correlation_age_seconds": correlation.get("age_seconds"),
        "dns_policy_state": ((document.get("components") or {}).get("dns_policy") or {}).get("state"),
        "enforcement_enabled": False,
        "traffic_controls_changed": False,
    }


def validate_acceptance(
    correlation_document: dict[str, Any],
    network_defense_document: dict[str, Any],
    now: dt.datetime | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    current = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    maximum = max(1, int(max_age_seconds))
    return {
        "ok": True,
        "verified_at": current.isoformat(),
        "read_only": True,
        "traffic_controls_changed": False,
        "correlation": validate_correlation(correlation_document, current, maximum),
        "network_defense": validate_network_defense(network_defense_document, current, maximum),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--correlation", type=Path, required=True)
    parser.add_argument("--network-defense", type=Path, required=True)
    parser.add_argument("--max-age-seconds", type=int, default=DEFAULT_MAX_AGE_SECONDS)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = validate_acceptance(
        load_document(args.correlation, "correlation"),
        load_document(args.network_defense, "Network Defense"),
        max_age_seconds=args.max_age_seconds,
    )
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
