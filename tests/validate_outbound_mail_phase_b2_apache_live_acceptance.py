#!/usr/bin/env python3
"""Validate the durable Phase B2 Apache live-acceptance record."""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / ".agent/outbound-mail-b2-apache-live-acceptance.md"
DOC = ROOT / "docs/messaging-operations/outbound-mail-phase-b2-apache-live-acceptance-20260801.md"

for path in (STATE, DOC):
    assert path.is_file(), path

state = STATE.read_text(encoding="utf-8")
doc = DOC.read_text(encoding="utf-8")
combined = state + "\n" + doc

for value in (
    "2026-08-01T22:10:05Z",
    "9bfc9d0c494da11a4fb47fe38e7390f0b12d1444",
    "d35fda6a3adcac2782ed6e8ed44ea8650a4d9df2",
    "/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-apache-proposal/20260801T210934Z",
    "/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-apache-activation/20260801T221005Z",
    "edge1.ww.cx",
    "162.0.217.71/32",
    "/etc/apache2/wwcx-outbound-mail-preparation-api.conf",
    "/etc/apache2/sites-enabled/edge1.ww.cx.conf",
    "/etc/apache2/sites-available/edge1.ww.cx.conf",
    "IncludeOptional /etc/apache2/wwcx-outbound-mail-preparation-api.conf",
    "127.0.0.1:8104",
    "Syntax OK",
    "activation_summary_validation=PASS",
    "B2_APACHE_ACTIVATION=PASS",
    "readiness_state=awaiting_business159_source_acceptance",
    "certificate private key exposed: no",
    "HMAC secret read or disclosed: no",
    "external delivery enabled: no",
    "message sent: no",
):
    assert value in combined, value

for value in (
    "status: HTTP `403`",
    "preparation request: HTTP `403`",
    "send route: HTTP `404`",
    "health route: HTTP `404`",
    "health: HTTP `200`",
    "unsigned preparation status: HTTP `401`",
    "send: HTTP `403`",
):
    assert value in state, value

for value in (
    "status  = 403",
    "prepare = 403",
    "send    = 404",
    "health  = 404",
    "unsigned status = 401",
    "external_delivery_enabled=false",
    "live_sender_count=0",
    "providers_ready=0",
):
    assert value in doc, value

assert "website bridge enabled: no" in state
assert "provider or sender enabled: no" in state
assert "No rollback was required" in doc
assert "credential-free canary from business159" in doc
assert "production delivery and any actual message remain out of scope" in doc

for forbidden in (
    "website bridge enabled: yes",
    "external delivery enabled: yes",
    "message sent: yes",
    "production message sent",
    "HMAC secret value",
    "private key contents",
):
    assert forbidden not in combined, forbidden

print("Outbound mail Phase B2 Apache live acceptance validation passed")
print("Exact-route activation and evidence are recorded as accepted")
print("Business159 source acceptance, bridge credentials, and delivery remain gated")
