#!/usr/bin/env python3
"""Conservative informational indicators over aggregate telephony summaries.

This module consumes only the privacy-minimized output contracts produced by
telephony_platform.py. It performs no source access, notification, enforcement,
blocking, routing, service control, or automatic remediation.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

SCHEMA_VERSION = "1.0"
MODE = "informational_no_enforcement"

STATE_RANK = {
    "insufficient_data": 0,
    "ok": 1,
    "watch": 2,
    "critical": 3,
}

HEALTH_FIELDS = {"score", "overall_status", "components"}
HEALTH_COMPONENTS = {"pbx", "sip", "routing", "registry", "analytics"}
HEALTH_STATES = {"healthy", "pass", "ready", "degraded", "warn", "unknown", "critical", "fail"}

CALL_FIELDS = {
    "calls_total",
    "calls_answered",
    "answer_rate_percent",
    "duration_seconds_total",
    "duration_seconds_average",
    "directions",
    "dispositions",
    "carriers",
    "destination_countries",
    "sip_codes",
    "failure_classes",
}

INTERCONNECT_FIELDS = {
    "interconnects_total",
    "states",
    "latency_ms_average",
    "latency_ms_max",
    "attention_required",
}

SAFE_AGGREGATE_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,63}$")
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
    """Raised when an aggregate summary is outside the accepted contract."""


def _exact_fields(value: Mapping[str, Any], expected: set[str], name: str) -> None:
    if not isinstance(value, Mapping):
        raise AnomalyIndicatorError(f"{name} must be a mapping")
    keys = set(value)
    if keys != expected:
        missing = sorted(expected - keys)
        extra = sorted(keys - expected)
        raise AnomalyIndicatorError(f"{name} fields do not match contract; missing={missing} extra={extra}")


def _nonnegative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise AnomalyIndicatorError(f"{field_name} must be a non-negative integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise AnomalyIndicatorError(f"{field_name} must be a non-negative integer") from exc
    if result < 0 or result != value:
        raise AnomalyIndicatorError(f"{field_name} must be a non-negative integer")
    return result


def _bounded_number(value: Any, field_name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        raise AnomalyIndicatorError(f"{field_name} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise AnomalyIndicatorError(f"{field_name} must be numeric") from exc
    if not math.isfinite(result) or result < minimum or result > maximum:
        raise AnomalyIndicatorError(f"{field_name} is outside the accepted range")
    return result


def _optional_latency(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    return _bounded_number(value, field_name, 0.0, 86_400_000.0)


def _safe_aggregate_key(value: Any, field_name: str) -> str:
    key = str(value)
    if not SAFE_AGGREGATE_KEY_RE.fullmatch(key):
        raise AnomalyIndicatorError(f"{field_name} contains an unsupported aggregate key")
    if LONG_DIGIT_RE.search(key) or EMAIL_RE.search(key) or URI_RE.search(key) or IPV4_RE.search(key):
        raise AnomalyIndicatorError(f"{field_name} contains a customer identifier or address")
    return key


def _count_map(value: Any, field_name: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise AnomalyIndicatorError(f"{field_name} must be a mapping")
    result: dict[str, int] = {}
    for key, count in value.items():
        safe_key = _safe_aggregate_key(key, field_name)
        if safe_key in result:
            raise AnomalyIndicatorError(f"{field_name} contains a duplicate aggregate key")
        result[safe_key] = _nonnegative_int(count, f"{field_name}.{safe_key}")
    return result


def _validate_health(summary: Mapping[str, Any]) -> dict[str, Any]:
    _exact_fields(summary, HEALTH_FIELDS, "health_summary")
    score = _bounded_number(summary["score"], "health_summary.score", 0.0, 100.0)
    overall_status = str(summary["overall_status"]).lower()
    if overall_status not in {"healthy", "degraded", "critical"}:
        raise AnomalyIndicatorError("health_summary.overall_status is unsupported")
    components = summary["components"]
    if not isinstance(components, Mapping) or set(components) != HEALTH_COMPONENTS:
        raise AnomalyIndicatorError("health_summary.components do not match the expected component set")
    normalized_components: dict[str, str] = {}
    for component in sorted(HEALTH_COMPONENTS):
        state = str(components[component]).lower()
        if state not in HEALTH_STATES:
            raise AnomalyIndicatorError(f"health_summary.components.{component} is unsupported")
        normalized_components[component] = state
    return {
        "score": score,
        "overall_status": overall_status,
        "components": normalized_components,
    }


def _validate_calls(summary: Mapping[str, Any]) -> dict[str, Any]:
    _exact_fields(summary, CALL_FIELDS, "call_summary")
    calls_total = _nonnegative_int(summary["calls_total"], "call_summary.calls_total")
    calls_answered = _nonnegative_int(summary["calls_answered"], "call_summary.calls_answered")
    if calls_answered > calls_total:
        raise AnomalyIndicatorError("call_summary.calls_answered exceeds calls_total")
    answer_rate = _bounded_number(summary["answer_rate_percent"], "call_summary.answer_rate_percent", 0.0, 100.0)
    expected_rate = round((calls_answered / calls_total) * 100, 2) if calls_total else 0.0
    if abs(answer_rate - expected_rate) > 0.01:
        raise AnomalyIndicatorError("call_summary.answer_rate_percent is inconsistent")
    duration_total = _nonnegative_int(summary["duration_seconds_total"], "call_summary.duration_seconds_total")
    duration_average = _bounded_number(
        summary["duration_seconds_average"],
        "call_summary.duration_seconds_average",
        0.0,
        604800.0,
    )
    if calls_total == 0 and (duration_total != 0 or duration_average != 0.0):
        raise AnomalyIndicatorError("empty call summary contains duration values")

    directions = _count_map(summary["directions"], "call_summary.directions")
    dispositions = _count_map(summary["dispositions"], "call_summary.dispositions")
    carriers = _count_map(summary["carriers"], "call_summary.carriers")
    destinations = _count_map(summary["destination_countries"], "call_summary.destination_countries")
    sip_codes = _count_map(summary["sip_codes"], "call_summary.sip_codes")
    failures = _count_map(summary["failure_classes"], "call_summary.failure_classes")

    for field_name, values in (
        ("directions", directions),
        ("dispositions", dispositions),
        ("carriers", carriers),
        ("destination_countries", destinations),
        ("sip_codes", sip_codes),
    ):
        if sum(values.values()) != calls_total:
            raise AnomalyIndicatorError(f"call_summary.{field_name} counts do not equal calls_total")
    if sum(failures.values()) > calls_total:
        raise AnomalyIndicatorError("call_summary.failure_classes exceeds calls_total")

    return {
        "calls_total": calls_total,
        "calls_answered": calls_answered,
        "answer_rate_percent": answer_rate,
        "duration_seconds_total": duration_total,
        "duration_seconds_average": duration_average,
        "directions": directions,
        "dispositions": dispositions,
        "carriers": carriers,
        "destination_countries": destinations,
        "sip_codes": sip_codes,
        "failure_classes": failures,
    }


def _validate_interconnects(summary: Mapping[str, Any]) -> dict[str, Any]:
    _exact_fields(summary, INTERCONNECT_FIELDS, "interconnect_summary")
    total = _nonnegative_int(summary["interconnects_total"], "interconnect_summary.interconnects_total")
    states = _count_map(summary["states"], "interconnect_summary.states")
    if sum(states.values()) != total:
        raise AnomalyIndicatorError("interconnect_summary.states counts do not equal interconnects_total")
    attention = _nonnegative_int(summary["attention_required"], "interconnect_summary.attention_required")
    if attention > total:
        raise AnomalyIndicatorError("interconnect_summary.attention_required exceeds interconnects_total")
    latency_average = _optional_latency(summary["latency_ms_average"], "interconnect_summary.latency_ms_average")
    latency_max = _optional_latency(summary["latency_ms_max"], "interconnect_summary.latency_ms_max")
    if (latency_average is None) != (latency_max is None):
        raise AnomalyIndicatorError("interconnect latency average and maximum must both be present or absent")
    if latency_average is not None and latency_max is not None and latency_average > latency_max:
        raise AnomalyIndicatorError("interconnect latency average exceeds maximum")
    if total == 0 and (latency_average is not None or latency_max is not None):
        raise AnomalyIndicatorError("empty interconnect summary contains latency values")
    return {
        "interconnects_total": total,
        "states": states,
        "latency_ms_average": latency_average,
        "latency_ms_max": latency_max,
        "attention_required": attention,
    }


def _state_below(value: float, watch_below: float, critical_below: float) -> str:
    if value < critical_below:
        return "critical"
    if value < watch_below:
        return "watch"
    return "ok"


def _state_at_or_above(value: float, watch_at: float, critical_at: float) -> str:
    if value >= critical_at:
        return "critical"
    if value >= watch_at:
        return "watch"
    return "ok"


def _indicator(
    indicator_id: str,
    state: str,
    observed_value: int | float | None,
    unit: str,
    minimum_sample: int,
    sample_size: int,
    thresholds: Mapping[str, int | float],
    reason_code: str,
    investigation_target: str,
) -> dict[str, Any]:
    if state not in STATE_RANK:
        raise AnomalyIndicatorError("internal indicator state is unsupported")
    return {
        "id": indicator_id,
        "state": state,
        "observed_value": observed_value,
        "unit": unit,
        "minimum_sample": minimum_sample,
        "sample_size": sample_size,
        "thresholds": dict(thresholds),
        "reason_code": reason_code,
        "investigation_target": investigation_target,
        "automatic_action": False,
    }


def evaluate_anomaly_indicators(
    health_summary: Mapping[str, Any],
    call_summary: Mapping[str, Any],
    interconnect_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Return deterministic informational indicators over accepted aggregates."""
    health = _validate_health(health_summary)
    calls = _validate_calls(call_summary)
    interconnects = _validate_interconnects(interconnect_summary)
    indicators: list[dict[str, Any]] = []

    health_state = _state_below(health["score"], 90.0, 60.0)
    indicators.append(_indicator(
        "platform_health_score",
        health_state,
        health["score"],
        "score",
        1,
        1,
        {"watch_below": 90.0, "critical_below": 60.0},
        f"platform_health_{health_state}",
        "#analytics-health",
    ))

    call_count = calls["calls_total"]
    if call_count < MIN_CALL_SAMPLE:
        answer_state = "insufficient_data"
    else:
        answer_state = _state_below(
            calls["answer_rate_percent"],
            ANSWER_RATE_WATCH_BELOW,
            ANSWER_RATE_CRITICAL_BELOW,
        )
    indicators.append(_indicator(
        "answer_rate",
        answer_state,
        calls["answer_rate_percent"],
        "percent",
        MIN_CALL_SAMPLE,
        call_count,
        {
            "watch_below": ANSWER_RATE_WATCH_BELOW,
            "critical_below": ANSWER_RATE_CRITICAL_BELOW,
        },
        f"answer_rate_{answer_state}",
        "#analytics-failures",
    ))

    failure_count = sum(calls["failure_classes"].values())
    failure_ratio = round((failure_count / call_count) * 100, 2) if call_count else 0.0
    if call_count < MIN_CALL_SAMPLE:
        failure_state = "insufficient_data"
    else:
        failure_state = _state_at_or_above(
            failure_ratio,
            FAILURE_RATIO_WATCH_AT,
            FAILURE_RATIO_CRITICAL_AT,
        )
    indicators.append(_indicator(
        "failure_ratio",
        failure_state,
        failure_ratio,
        "percent",
        MIN_CALL_SAMPLE,
        call_count,
        {
            "watch_at_or_above": FAILURE_RATIO_WATCH_AT,
            "critical_at_or_above": FAILURE_RATIO_CRITICAL_AT,
        },
        f"failure_ratio_{failure_state}",
        "#analytics-failures",
    ))

    if failure_count:
        dominant_failure_count = max(calls["failure_classes"].values())
        dominant_failure_share = round((dominant_failure_count / failure_count) * 100, 2)
    else:
        dominant_failure_share = 0.0
    if failure_count < MIN_FAILURE_SAMPLE:
        dominant_state = "insufficient_data"
    else:
        dominant_state = _state_at_or_above(
            dominant_failure_share,
            DOMINANT_FAILURE_WATCH_AT,
            DOMINANT_FAILURE_CRITICAL_AT,
        )
    indicators.append(_indicator(
        "dominant_failure_concentration",
        dominant_state,
        dominant_failure_share,
        "percent",
        MIN_FAILURE_SAMPLE,
        failure_count,
        {
            "watch_at_or_above": DOMINANT_FAILURE_WATCH_AT,
            "critical_at_or_above": DOMINANT_FAILURE_CRITICAL_AT,
        },
        f"dominant_failure_{dominant_state}",
        "#analytics-failures",
    ))

    interconnect_count = interconnects["interconnects_total"]
    attention_ratio = round(
        (interconnects["attention_required"] / interconnect_count) * 100,
        2,
    ) if interconnect_count else 0.0
    if interconnect_count < MIN_INTERCONNECT_SAMPLE:
        attention_state = "insufficient_data"
    else:
        attention_state = _state_at_or_above(
            attention_ratio,
            INTERCONNECT_ATTENTION_WATCH_AT,
            INTERCONNECT_ATTENTION_CRITICAL_AT,
        )
    indicators.append(_indicator(
        "interconnect_attention_ratio",
        attention_state,
        attention_ratio,
        "percent",
        MIN_INTERCONNECT_SAMPLE,
        interconnect_count,
        {
            "watch_at_or_above": INTERCONNECT_ATTENTION_WATCH_AT,
            "critical_at_or_above": INTERCONNECT_ATTENTION_CRITICAL_AT,
        },
        f"interconnect_attention_{attention_state}",
        "#analytics-carriers",
    ))

    latency_average = interconnects["latency_ms_average"]
    latency_max = interconnects["latency_ms_max"]
    if interconnect_count < MIN_INTERCONNECT_SAMPLE or latency_average is None or latency_max is None:
        latency_state = "insufficient_data"
        latency_observed = None
    else:
        latency_observed = latency_average
        if latency_average >= LATENCY_AVERAGE_CRITICAL_AT or latency_max >= LATENCY_MAX_CRITICAL_AT:
            latency_state = "critical"
        elif latency_average >= LATENCY_AVERAGE_WATCH_AT or latency_max >= LATENCY_MAX_WATCH_AT:
            latency_state = "watch"
        else:
            latency_state = "ok"
    indicators.append(_indicator(
        "interconnect_latency",
        latency_state,
        latency_observed,
        "milliseconds_average",
        MIN_INTERCONNECT_SAMPLE,
        interconnect_count,
        {
            "average_watch_at_or_above": LATENCY_AVERAGE_WATCH_AT,
            "average_critical_at_or_above": LATENCY_AVERAGE_CRITICAL_AT,
            "maximum_watch_at_or_above": LATENCY_MAX_WATCH_AT,
            "maximum_critical_at_or_above": LATENCY_MAX_CRITICAL_AT,
        },
        f"interconnect_latency_{latency_state}",
        "#analytics-carriers",
    ))

    actionable_states = [item["state"] for item in indicators if item["state"] != "insufficient_data"]
    if actionable_states:
        overall_state = max(actionable_states, key=lambda state: STATE_RANK[state])
    else:
        overall_state = "insufficient_data"

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "overall_state": overall_state,
        "indicators": indicators,
        "safety": {
            "automatic_action": False,
            "notification_dispatch": False,
            "traffic_enforcement": False,
            "route_change": False,
            "service_control": False,
        },
    }
