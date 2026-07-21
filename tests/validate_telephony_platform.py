#!/usr/bin/env python3
"""Focused validation for the read-only telephony operations platform."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from telephony_platform import (  # noqa: E402
    CallEvent,
    analyze_interconnects,
    classify_sip_failure,
    health_score,
    summarize_calls,
)

MODULE = ROOT / "server" / "telephony_platform.py"
DOC = ROOT / "docs" / "telephony" / "operations-platform.md"
REGISTER = ROOT / "docs" / "project-register" / "wwcx-telephony-operations-platform.md"

for path in (MODULE, DOC, REGISTER):
    if not path.is_file():
        raise SystemExit(f"missing telephony platform asset: {path.relative_to(ROOT)}")

ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))

assert classify_sip_failure(200) == "success_or_progress"
assert classify_sip_failure(403) == "authorization_or_policy_rejection"
assert classify_sip_failure(488) == "media_or_codec_negotiation"
assert classify_sip_failure(503) == "service_unavailable"
assert classify_sip_failure(None) == "unclassified"

healthy = health_score(
    {
        "pbx": "healthy",
        "sip": "healthy",
        "routing": "pass",
        "registry": "ready",
        "analytics": "healthy",
    }
)
assert healthy["score"] == 100
assert healthy["overall_status"] == "healthy"

degraded = health_score(
    {
        "pbx": "healthy",
        "sip": "warn",
        "routing": "pass",
        "registry": "ready",
        "analytics": "unknown",
    }
)
assert 60 <= degraded["score"] < 90
assert degraded["overall_status"] == "degraded"

events = [
    CallEvent("outbound", "answered", 200, "carrier-a", "CA", 90),
    CallEvent("outbound", "failed", 503, "carrier-a", "US", 0),
    CallEvent("inbound", "completed", 200, "carrier-b", "CA", 30),
]
summary = summarize_calls(events)
assert summary["calls_total"] == 3
assert summary["calls_answered"] == 2
assert summary["answer_rate_percent"] == 66.67
assert summary["failure_classes"] == {"service_unavailable": 1}
assert summary["duration_seconds_total"] == 120

interconnects = analyze_interconnects(
    [
        {"status": "healthy", "latency_ms": 20},
        {"status": "degraded", "latency_ms": 60},
        {"status": "unknown", "latency_ms": None},
    ]
)
assert interconnects["interconnects_total"] == 3
assert interconnects["latency_ms_average"] == 40.0
assert interconnects["attention_required"] == 2

for text, markers in (
    (
        DOC.read_text(encoding="utf-8"),
        (
            "Read-only production boundary",
            "Management and analysis capabilities",
            "Privacy and evidence",
            "Controlled follow-on",
        ),
    ),
    (
        REGISTER.read_text(encoding="utf-8"),
        ("Project status", "Delivered foundation", "Acceptance criteria", "Controlled blockers"),
    ),
):
    for marker in markers:
        if marker not in text:
            raise SystemExit(f"telephony platform documentation missing marker: {marker}")

print("telephony operations platform validation passed")
