#!/usr/bin/env python3
"""Validate conservative informational telephony anomaly indicators."""
from __future__ import annotations

import ast
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from telephony_anomaly_indicators import (  # noqa: E402
    AnomalyIndicatorError,
    evaluate_anomaly_indicators,
)
from telephony_platform import (  # noqa: E402
    CallEvent,
    analyze_interconnects,
    health_score,
    summarize_calls,
)

MODULE = ROOT / "server" / "telephony_anomaly_indicators.py"
DOC = ROOT / "docs" / "telephony" / "anomaly-indicators.md"
SCHEMA = ROOT / "schemas" / "telephony" / "anomaly-indicators.schema.json"

for path in (MODULE, DOC, SCHEMA):
    if not path.is_file():
        raise SystemExit(f"missing anomaly indicator asset: {path.relative_to(ROOT)}")

source = MODULE.read_text(encoding="utf-8")
ast.parse(source, filename=str(MODULE))

for marker in (
    'MODE = "informational_no_enforcement"',
    '"insufficient_data"',
    '"automatic_action": False',
    '"notification_dispatch": False',
    '"traffic_enforcement": False',
    '"route_change": False',
    '"service_control": False',
    '"#analytics-health"',
    '"#analytics-failures"',
    '"#analytics-carriers"',
):
    if marker not in source:
        raise SystemExit(f"anomaly indicator module missing marker: {marker}")

for forbidden in (
    "import socket",
    "import subprocess",
    "import sqlite3",
    "import urllib",
    "import requests",
    "systemctl",
    "asterisk -rx",
    "sendmail",
    "smtp",
    "webhook",
):
    if forbidden in source:
        raise SystemExit(f"anomaly indicator module contains prohibited action path: {forbidden}")


def event(answered: bool, sip_code: int, carrier: str = "carrier-a") -> CallEvent:
    return CallEvent(
        direction="outbound",
        disposition="answered" if answered else "failed",
        sip_code=sip_code,
        carrier_id=carrier,
        destination_country="CA",
        duration_seconds=30 if answered else 0,
    )


def summaries(
    answered: int,
    failures: list[int],
    interconnect_rows: list[dict[str, object]],
    components: dict[str, str] | None = None,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    total = max(20, answered + len(failures))
    events = [event(True, 200) for _ in range(answered)]
    events.extend(event(False, code) for code in failures)
    events.extend(event(False, 487) for _ in range(total - len(events)))
    health = health_score(components or {
        "pbx": "healthy",
        "sip": "healthy",
        "routing": "healthy",
        "registry": "healthy",
        "analytics": "healthy",
    })
    return health, summarize_calls(events), analyze_interconnects(interconnect_rows)


healthy_rows = [
    {"status": "healthy", "latency_ms": 30},
    {"status": "healthy", "latency_ms": 40},
    {"status": "healthy", "latency_ms": 50},
    {"status": "healthy", "latency_ms": 60},
]
health, calls, interconnects = summaries(18, [486, 486], healthy_rows)
healthy = evaluate_anomaly_indicators(health, calls, interconnects)
assert healthy["schema_version"] == "1.0"
assert healthy["mode"] == "informational_no_enforcement"
assert healthy["overall_state"] == "ok"
assert len(healthy["indicators"]) == 6
assert all(item["automatic_action"] is False for item in healthy["indicators"])
assert healthy["safety"] == {
    "automatic_action": False,
    "notification_dispatch": False,
    "traffic_enforcement": False,
    "route_change": False,
    "service_control": False,
}
assert calls["sip_codes"]["200"] == 18

insufficient_calls = summarize_calls([event(True, 200) for _ in range(5)])
insufficient_interconnects = analyze_interconnects([{"status": "healthy", "latency_ms": 20}])
insufficient = evaluate_anomaly_indicators(health, insufficient_calls, insufficient_interconnects)
by_id = {item["id"]: item for item in insufficient["indicators"]}
assert by_id["platform_health_score"]["state"] == "ok"
assert by_id["answer_rate"]["state"] == "insufficient_data"
assert by_id["failure_ratio"]["state"] == "insufficient_data"
assert by_id["dominant_failure_concentration"]["state"] == "insufficient_data"
assert by_id["interconnect_attention_ratio"]["state"] == "insufficient_data"
assert by_id["interconnect_latency"]["state"] == "insufficient_data"
assert insufficient["overall_state"] == "ok"

watch_rows = [
    {"status": "healthy", "latency_ms": 100},
    {"status": "healthy", "latency_ms": 200},
    {"status": "healthy", "latency_ms": 300},
    {"status": "degraded", "latency_ms": 800},
]
watch_health, watch_calls, watch_interconnects = summaries(12, [486] * 4 + [503] * 4, watch_rows)
watch = evaluate_anomaly_indicators(watch_health, watch_calls, watch_interconnects)
watch_by_id = {item["id"]: item for item in watch["indicators"]}
assert watch_by_id["answer_rate"]["state"] == "watch"
assert watch_by_id["failure_ratio"]["state"] == "watch"
assert watch_by_id["interconnect_attention_ratio"]["state"] == "watch"
assert watch_by_id["interconnect_latency"]["state"] == "watch"
assert watch["overall_state"] == "watch"

critical_rows = [
    {"status": "healthy", "latency_ms": 100},
    {"status": "healthy", "latency_ms": 200},
    {"status": "critical", "latency_ms": 600},
    {"status": "degraded", "latency_ms": 1500},
]
critical_health, critical_calls, critical_interconnects = summaries(
    8,
    [503] * 10 + [486] * 2,
    critical_rows,
    {
        "pbx": "critical",
        "sip": "critical",
        "routing": "degraded",
        "registry": "healthy",
        "analytics": "healthy",
    },
)
critical = evaluate_anomaly_indicators(critical_health, critical_calls, critical_interconnects)
critical_by_id = {item["id"]: item for item in critical["indicators"]}
assert critical_by_id["platform_health_score"]["state"] == "critical"
assert critical_by_id["answer_rate"]["state"] == "critical"
assert critical_by_id["failure_ratio"]["state"] == "critical"
assert critical_by_id["dominant_failure_concentration"]["state"] == "critical"
assert critical_by_id["interconnect_attention_ratio"]["state"] == "critical"
assert critical_by_id["interconnect_latency"]["state"] == "critical"
assert critical["overall_state"] == "critical"

boundary_calls = summarize_calls(
    [event(True, 200) for _ in range(14)] + [event(False, 486) for _ in range(6)]
)
boundary = evaluate_anomaly_indicators(health, boundary_calls, interconnects)
boundary_by_id = {item["id"]: item for item in boundary["indicators"]}
assert boundary_by_id["answer_rate"]["state"] == "ok"
assert boundary_by_id["failure_ratio"]["state"] == "watch"

private_tokens = {"carrier-a", "busy", "service_unavailable", "CA", "200", "486", "503"}
serialized = repr(critical)
for token in private_tokens:
    assert token not in serialized

for indicator in critical["indicators"]:
    assert indicator["investigation_target"] in {
        "#analytics-health",
        "#analytics-failures",
        "#analytics-carriers",
    }
    assert set(indicator) == {
        "id", "state", "observed_value", "unit", "minimum_sample",
        "sample_size", "thresholds", "reason_code", "investigation_target",
        "automatic_action",
    }


def rejected(health_value: dict[str, object], calls_value: dict[str, object], interconnect_value: dict[str, object], expected: str) -> None:
    try:
        evaluate_anomaly_indicators(health_value, calls_value, interconnect_value)
    except AnomalyIndicatorError as exc:
        if expected not in str(exc):
            raise AssertionError(f"unexpected rejection: {exc}") from exc
    else:
        raise AssertionError("invalid aggregate summary was accepted")

unsafe_calls = copy.deepcopy(calls)
unsafe_calls["caller_id"] = "+1 555 010 0200"
rejected(health, unsafe_calls, interconnects, "fields do not match contract")

unsafe_calls = copy.deepcopy(calls)
unsafe_calls["carriers"] = {"carrier-123456789": calls["calls_total"]}
rejected(health, unsafe_calls, interconnects, "customer identifier")

unsafe_calls = copy.deepcopy(calls)
unsafe_calls["calls_answered"] = calls["calls_total"] + 1
rejected(health, unsafe_calls, interconnects, "exceeds calls_total")

unsafe_calls = copy.deepcopy(calls)
unsafe_calls["duration_seconds_average"] = 999.0
rejected(health, unsafe_calls, interconnects, "duration_seconds_average is inconsistent")

unsafe_health = copy.deepcopy(health)
unsafe_health["overall_status"] = "critical"
rejected(unsafe_health, calls, interconnects, "inconsistent with score")

unsafe_interconnects = copy.deepcopy(interconnects)
unsafe_interconnects["attention_required"] = 1
rejected(health, calls, unsafe_interconnects, "inconsistent with states")

unsafe_interconnects = copy.deepcopy(interconnects)
unsafe_interconnects["latency_ms_average"] = 1000
unsafe_interconnects["latency_ms_max"] = 500
rejected(health, calls, unsafe_interconnects, "average exceeds maximum")

schema_source = SCHEMA.read_text(encoding="utf-8")
for marker in (
    '"informational_no_enforcement"',
    '"insufficient_data"',
    '"automatic_action"',
    '"const": false',
):
    if marker not in schema_source:
        raise SystemExit(f"anomaly indicator schema missing marker: {marker}")

doc_source = DOC.read_text(encoding="utf-8")
for marker in (
    "Aggregate-only input boundary",
    "Minimum sample gates",
    "Fixed informational thresholds",
    "No notification or enforcement",
    "Static investigation targets",
):
    if marker not in doc_source:
        raise SystemExit(f"anomaly indicator documentation missing marker: {marker}")

print("telephony anomaly indicator validation passed")
