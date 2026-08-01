#!/usr/bin/env python3
"""Conservative informational indicators over aggregate telephony summaries.

The evaluator consumes only privacy-minimized aggregate contracts. It performs
no source access, notification, enforcement, blocking, routing, service control,
or automatic remediation.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

SCHEMA_VERSION = "1.0"
MODE = "informational_no_enforcement"
STATES = {"insufficient_data", "ok", "watch", "critical"}
STATE_RANK = {"insufficient_data": 0, "ok": 1, "watch": 2, "critical": 3}

HEALTH_FIELDS = {"score", "overall_status", "components"}
HEALTH_COMPONENTS = {"pbx", "sip", "routing", "registry", "analytics"}
HEALTH_STATES = {"healthy", "pass", "ready", "degraded", "warn", "unknown", "critical", "fail"}
CALL_FIELDS = {
    "calls_total", "calls_answered", "answer_rate_percent",
    "duration_seconds_total", "duration_seconds_average", "directions",
    "dispositions", "carriers", "destination_countries", "sip_codes",
    "failure_classes",
}
INTERCONNECT_FIELDS = {
    "interconnects_total", "states", "latency_ms_average",
    "latency_ms_max", "attention_required",
}

SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
LONG_DIGIT_RE = re.compile(r"[0-9]{7,}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URI_RE = re.compile(r"\b(?:sip|sips|tel|http|https):", re.IGNORECASE)
IPV4_RE = re.compile(r"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])")

MIN_CALL_SAMPLE = 20
MIN_FAILURE_SAMPLE = 10
MIN_INTERCONNECT_SAMPLE = 2
ANSWER_RATE_WATCH_BELOW = 70.0
ANSWER_RATE_CRITICAL_BELOW = 50.0
FAILURE_RATIO_WATCH_AT = 25.0
FAILURE_RATIO_CRITICAL_AT = 50.0
DOMINANT_FAILURE_WATCH_AT = 60.0
DOMINANT_FAILURE_CRITICAL_AT = 80.0
INTERCONNECT_ATTENTION_WATCH_AT = 25.0
INTERCONNECT_ATTENTION_CRITICAL_AT = 50.0
LATENCY_AVERAGE_WATCH_AT = 250.0
LATENCY_AVERAGE_CRITICAL_AT = 500.0
LATENCY_MAX_WATCH_AT = 750.0
LATENCY_MAX_CRITICAL_AT = 1500.0


class AnomalyIndicatorError(ValueError):
    """Raised when an aggregate summary violates the accepted contract."""


def _exact_fields(value: Any, expected: set[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AnomalyIndicatorError(f"{name} must be a mapping")
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise AnomalyIndicatorError(f"{name} fields do not match contract; missing={missing} extra={extra}")
    return value


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AnomalyIndicatorError(f"{name} must be a non-negative integer")
    return value


def _number(value: Any, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnomalyIndicatorError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise AnomalyIndicatorError(f"{name} is outside the accepted range")
    return result


def _optional_latency(value: Any, name: str) -> float | None:
    return None if value is None else _number(value, name, 0.0, 86_400_000.0)


def _safe_key(value: Any, name: str) -> str:
    key = str(value)
    if not SAFE_KEY_RE.fullmatch(key):
        raise AnomalyIndicatorError(f"{name} contains an unsupported aggregate key")
    if LONG_DIGIT_RE.search(key) or EMAIL_RE.search(key) or URI_RE.search(key) or IPV4_RE.search(key):
        raise AnomalyIndicatorError(f"{name} contains a customer identifier or address")
    return key


def _count_map(value: Any, name: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise AnomalyIndicatorError(f"{name} must be a mapping")
    result: dict[str, int] = {}
    for raw_key, raw_count in value.items():
        key = _safe_key(raw_key, name)
        if key in result:
            raise AnomalyIndicatorError(f"{name} contains a duplicate aggregate key")
        result[key] = _integer(raw_count, f"{name}.{key}")
    return result


def _health(summary: Any) -> dict[str, Any]:
    value = _exact_fields(summary, HEALTH_FIELDS, "health_summary")
    score = _number(value["score"], "health_summary.score", 0.0, 100.0)
    overall = str(value["overall_status"]).lower()
    if overall not in {"healthy", "degraded", "critical"}:
        raise AnomalyIndicatorError("health_summary.overall_status is unsupported")
    components = value["components"]
    if not isinstance(components, Mapping) or set(components) != HEALTH_COMPONENTS:
        raise AnomalyIndicatorError("health_summary.components do not match the expected component set")
    normalized: dict[str, str] = {}
    for component in sorted(HEALTH_COMPONENTS):
        state = str(components[component]).lower()
        if state not in HEALTH_STATES:
            raise AnomalyIndicatorError(f"health_summary.components.{component} is unsupported")
        normalized[component] = state
    expected_overall = "healthy" if score >= 90 else ("degraded" if score >= 60 else "critical")
    if overall != expected_overall:
        raise AnomalyIndicatorError("health_summary.overall_status is inconsistent with score")
    return {"score": score, "overall_status": overall, "components": normalized}


def _calls(summary: Any) -> dict[str, Any]:
    value = _exact_fields(summary, CALL_FIELDS, "call_summary")
    total = _integer(value["calls_total"], "call_summary.calls_total")
    answered = _integer(value["calls_answered"], "call_summary.calls_answered")
    if answered > total:
        raise AnomalyIndicatorError("call_summary.calls_answered exceeds calls_total")
    rate = _number(value["answer_rate_percent"], "call_summary.answer_rate_percent", 0.0, 100.0)
    expected_rate = round((answered / total) * 100, 2) if total else 0.0
    if abs(rate - expected_rate) > 0.01:
        raise AnomalyIndicatorError("call_summary.answer_rate_percent is inconsistent")
    duration_total = _integer(value["duration_seconds_total"], "call_summary.duration_seconds_total")
    duration_average = _number(value["duration_seconds_average"], "call_summary.duration_seconds_average", 0.0, 604800.0)
    expected_average = round(duration_total / total, 2) if total else 0.0
    if abs(duration_average - expected_average) > 0.01:
        raise AnomalyIndicatorError("call_summary.duration_seconds_average is inconsistent")

    maps = {
        name: _count_map(value[name], f"call_summary.{name}")
        for name in (
            "directions", "dispositions", "carriers", "destination_countries",
            "sip_codes", "failure_classes",
        )
    }
    for name in ("directions", "dispositions", "carriers", "destination_countries", "sip_codes"):
        if sum(maps[name].values()) != total:
            raise AnomalyIndicatorError(f"call_summary.{name} counts do not equal calls_total")
    if sum(maps["failure_classes"].values()) > total:
        raise AnomalyIndicatorError("call_summary.failure_classes exceeds calls_total")
    return {
        "calls_total": total,
        "calls_answered": answered,
        "answer_rate_percent": rate,
        "duration_seconds_total": duration_total,
        "duration_seconds_average": duration_average,
        **maps,
    }


def _interconnects(summary: Any) -> dict[str, Any]:
    value = _exact_fields(summary, INTERCONNECT_FIELDS, "interconnect_summary")
    total = _integer(value["interconnects_total"], "interconnect_summary.interconnects_total")
    states = _count_map(value["states"], "interconnect_summary.states")
    if sum(states.values()) != total:
        raise AnomalyIndicatorError("interconnect_summary.states counts do not equal interconnects_total")
    attention = _integer(value["attention_required"], "interconnect_summary.attention_required")
    expected_attention = sum(count for state, count in states.items() if state not in {"healthy", "pass", "ready"})
    if attention != expected_attention:
        raise AnomalyIndicatorError("interconnect_summary.attention_required is inconsistent with states")
    average = _optional_latency(value["latency_ms_average"], "interconnect_summary.latency_ms_average")
    maximum = _optional_latency(value["latency_ms_max"], "interconnect_summary.latency_ms_max")
    if (average is None) != (maximum is None):
        raise AnomalyIndicatorError("interconnect latency average and maximum must both be present or absent")
    if average is not None and maximum is not None and average > maximum:
        raise AnomalyIndicatorError("interconnect latency average exceeds maximum")
    if total == 0 and average is not None:
        raise AnomalyIndicatorError("empty interconnect summary contains latency values")
    return {
        "interconnects_total": total,
        "states": states,
        "latency_ms_average": average,
        "latency_ms_max": maximum,
        "attention_required": attention,
    }


def _below(value: float, watch: float, critical: float) -> str:
    return "critical" if value < critical else ("watch" if value < watch else "ok")


def _above(value: float, watch: float, critical: float) -> str:
    return "critical" if value >= critical else ("watch" if value >= watch else "ok")


def _indicator(
    indicator_id: str,
    state: str,
    observed: int | float | None,
    unit: str,
    minimum_sample: int,
    sample_size: int,
    thresholds: Mapping[str, int | float],
    target: str,
) -> dict[str, Any]:
    if state not in STATES:
        raise AnomalyIndicatorError("internal indicator state is unsupported")
    return {
        "id": indicator_id,
        "state": state,
        "observed_value": observed,
        "unit": unit,
        "minimum_sample": minimum_sample,
        "sample_size": sample_size,
        "thresholds": dict(thresholds),
        "reason_code": f"{indicator_id}_{state}",
        "investigation_target": target,
        "automatic_action": False,
    }


def evaluate_anomaly_indicators(
    health_summary: Mapping[str, Any],
    call_summary: Mapping[str, Any],
    interconnect_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Return deterministic informational indicators over accepted aggregates."""
    health = _health(health_summary)
    calls = _calls(call_summary)
    interconnects = _interconnects(interconnect_summary)
    indicators: list[dict[str, Any]] = []

    indicators.append(_indicator(
        "platform_health_score",
        _below(health["score"], 90.0, 60.0),
        health["score"], "score", 1, 1,
        {"watch_below": 90.0, "critical_below": 60.0},
        "#analytics-health",
    ))

    call_count = calls["calls_total"]
    answer_state = "insufficient_data" if call_count < MIN_CALL_SAMPLE else _below(
        calls["answer_rate_percent"], ANSWER_RATE_WATCH_BELOW, ANSWER_RATE_CRITICAL_BELOW
    )
    indicators.append(_indicator(
        "answer_rate", answer_state, calls["answer_rate_percent"], "percent",
        MIN_CALL_SAMPLE, call_count,
        {"watch_below": ANSWER_RATE_WATCH_BELOW, "critical_below": ANSWER_RATE_CRITICAL_BELOW},
        "#analytics-failures",
    ))

    failures = calls["failure_classes"]
    failure_count = sum(failures.values())
    failure_ratio = round((failure_count / call_count) * 100, 2) if call_count else 0.0
    failure_state = "insufficient_data" if call_count < MIN_CALL_SAMPLE else _above(
        failure_ratio, FAILURE_RATIO_WATCH_AT, FAILURE_RATIO_CRITICAL_AT
    )
    indicators.append(_indicator(
        "failure_ratio", failure_state, failure_ratio, "percent",
        MIN_CALL_SAMPLE, call_count,
        {"watch_at_or_above": FAILURE_RATIO_WATCH_AT, "critical_at_or_above": FAILURE_RATIO_CRITICAL_AT},
        "#analytics-failures",
    ))

    dominant_share = round((max(failures.values()) / failure_count) * 100, 2) if failure_count else 0.0
    dominant_state = "insufficient_data" if failure_count < MIN_FAILURE_SAMPLE else _above(
        dominant_share, DOMINANT_FAILURE_WATCH_AT, DOMINANT_FAILURE_CRITICAL_AT
    )
    indicators.append(_indicator(
        "dominant_failure_concentration", dominant_state, dominant_share, "percent",
        MIN_FAILURE_SAMPLE, failure_count,
        {"watch_at_or_above": DOMINANT_FAILURE_WATCH_AT, "critical_at_or_above": DOMINANT_FAILURE_CRITICAL_AT},
        "#analytics-failures",
    ))

    interconnect_count = interconnects["interconnects_total"]
    attention_ratio = round((interconnects["attention_required"] / interconnect_count) * 100, 2) if interconnect_count else 0.0
    attention_state = "insufficient_data" if interconnect_count < MIN_INTERCONNECT_SAMPLE else _above(
        attention_ratio, INTERCONNECT_ATTENTION_WATCH_AT, INTERCONNECT_ATTENTION_CRITICAL_AT
    )
    indicators.append(_indicator(
        "interconnect_attention_ratio", attention_state, attention_ratio, "percent",
        MIN_INTERCONNECT_SAMPLE, interconnect_count,
        {"watch_at_or_above": INTERCONNECT_ATTENTION_WATCH_AT, "critical_at_or_above": INTERCONNECT_ATTENTION_CRITICAL_AT},
        "#analytics-carriers",
    ))

    average = interconnects["latency_ms_average"]
    maximum = interconnects["latency_ms_max"]
    if interconnect_count < MIN_INTERCONNECT_SAMPLE or average is None or maximum is None:
        latency_state = "insufficient_data"
        latency_observed = None
    elif average >= LATENCY_AVERAGE_CRITICAL_AT or maximum >= LATENCY_MAX_CRITICAL_AT:
        latency_state, latency_observed = "critical", average
    elif average >= LATENCY_AVERAGE_WATCH_AT or maximum >= LATENCY_MAX_WATCH_AT:
        latency_state, latency_observed = "watch", average
    else:
        latency_state, latency_observed = "ok", average
    indicators.append(_indicator(
        "interconnect_latency", latency_state, latency_observed, "milliseconds_average",
        MIN_INTERCONNECT_SAMPLE, interconnect_count,
        {
            "average_watch_at_or_above": LATENCY_AVERAGE_WATCH_AT,
            "average_critical_at_or_above": LATENCY_AVERAGE_CRITICAL_AT,
            "maximum_watch_at_or_above": LATENCY_MAX_WATCH_AT,
            "maximum_critical_at_or_above": LATENCY_MAX_CRITICAL_AT,
        },
        "#analytics-carriers",
    ))

    considered = [item["state"] for item in indicators if item["state"] != "insufficient_data"]
    overall = max(considered, key=lambda state: STATE_RANK[state]) if considered else "insufficient_data"
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "overall_state": overall,
        "indicators": indicators,
        "safety": {
            "automatic_action": False,
            "notification_dispatch": False,
            "traffic_enforcement": False,
            "route_change": False,
            "service_control": False,
        },
    }
