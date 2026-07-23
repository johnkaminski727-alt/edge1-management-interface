#!/usr/bin/env python3
"""Normalized read-only management and analysis helpers for telephony data.

This module deliberately contains no PBX, carrier, routing, credential, or
configuration write path. Collectors may pass sanitized records into these
helpers and expose the resulting summaries through the loopback-only console.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

HEALTH_WEIGHTS = {
    "pbx": 30,
    "sip": 25,
    "routing": 20,
    "registry": 15,
    "analytics": 10,
}

STATUS_SCORE = {
    "healthy": 1.0,
    "pass": 1.0,
    "ready": 1.0,
    "degraded": 0.5,
    "warn": 0.5,
    "unknown": 0.0,
    "critical": 0.0,
    "fail": 0.0,
}

SIP_FAILURE_CLASSES = {
    400: "request_error",
    401: "authentication_required",
    403: "authorization_or_policy_rejection",
    404: "destination_not_found",
    408: "request_timeout",
    480: "temporarily_unavailable",
    486: "busy",
    487: "request_terminated",
    488: "media_or_codec_negotiation",
    500: "upstream_server_error",
    502: "upstream_gateway_error",
    503: "service_unavailable",
    504: "upstream_timeout",
    603: "declined",
}


@dataclass(frozen=True)
class CallEvent:
    """Sanitized call-event record suitable for aggregate analysis."""

    direction: str
    disposition: str
    sip_code: int | None = None
    carrier_id: str | None = None
    destination_country: str | None = None
    duration_seconds: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.direction not in {"inbound", "outbound", "internal", "unknown"}:
            raise ValueError("invalid call direction")
        if self.duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")
        if self.sip_code is not None and not 100 <= self.sip_code <= 699:
            raise ValueError("sip_code must be between 100 and 699")


def classify_sip_failure(code: int | None) -> str:
    """Return a stable, non-speculative operational classification."""
    if code is None:
        return "unclassified"
    if code < 300:
        return "success_or_progress"
    if code in SIP_FAILURE_CLASSES:
        return SIP_FAILURE_CLASSES[code]
    if 300 <= code < 400:
        return "redirection"
    if 400 <= code < 500:
        return "request_or_destination_failure"
    if 500 <= code < 600:
        return "server_or_upstream_failure"
    if 600 <= code < 700:
        return "global_failure"
    return "unclassified"


def health_score(components: Mapping[str, str]) -> dict[str, Any]:
    """Calculate a bounded weighted score from normalized component states."""
    weighted_total = 0.0
    available_weight = 0
    normalized: dict[str, str] = {}

    for component, weight in HEALTH_WEIGHTS.items():
        state = str(components.get(component, "unknown")).lower()
        normalized[component] = state
        weighted_total += weight * STATUS_SCORE.get(state, 0.0)
        available_weight += weight

    score = round((weighted_total / available_weight) * 100) if available_weight else 0
    if score >= 90:
        overall = "healthy"
    elif score >= 60:
        overall = "degraded"
    else:
        overall = "critical"

    return {"score": score, "overall_status": overall, "components": normalized}


def summarize_calls(events: Iterable[CallEvent]) -> dict[str, Any]:
    """Produce privacy-minimized aggregate call analytics."""
    rows = list(events)
    dispositions = Counter(event.disposition for event in rows)
    directions = Counter(event.direction for event in rows)
    carriers = Counter(event.carrier_id or "unknown" for event in rows)
    destinations = Counter(event.destination_country or "unknown" for event in rows)
    sip_codes = Counter(str(event.sip_code) if event.sip_code is not None else "unknown" for event in rows)
    failures = Counter(
        classify_sip_failure(event.sip_code)
        for event in rows
        if event.sip_code is None or event.sip_code >= 300
    )

    answered = sum(1 for event in rows if event.disposition.lower() in {"answered", "completed"})
    total_duration = sum(event.duration_seconds for event in rows)
    total = len(rows)

    return {
        "calls_total": total,
        "calls_answered": answered,
        "answer_rate_percent": round((answered / total) * 100, 2) if total else 0.0,
        "duration_seconds_total": total_duration,
        "duration_seconds_average": round(total_duration / total, 2) if total else 0.0,
        "directions": dict(sorted(directions.items())),
        "dispositions": dict(sorted(dispositions.items())),
        "carriers": dict(carriers.most_common()),
        "destination_countries": dict(destinations.most_common()),
        "sip_codes": dict(sip_codes.most_common()),
        "failure_classes": dict(failures.most_common()),
    }


def analyze_interconnects(interconnects: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize normalized trunk/interconnect health without probing networks."""
    rows = list(interconnects)
    states = Counter(str(row.get("status", "unknown")).lower() for row in rows)
    latencies = [
        float(row["latency_ms"])
        for row in rows
        if isinstance(row.get("latency_ms"), (int, float))
    ]
    return {
        "interconnects_total": len(rows),
        "states": dict(sorted(states.items())),
        "latency_ms_average": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "latency_ms_max": max(latencies) if latencies else None,
        "attention_required": sum(
            count for state, count in states.items() if state not in {"healthy", "pass", "ready"}
        ),
    }
