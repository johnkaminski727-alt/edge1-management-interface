#!/usr/bin/env python3
"""Validate the recorded live acceptance of outbound-mail Phase B1."""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / ".agent/outbound-mail-activation.md"
ACCEPTANCE = (
    ROOT
    / "docs/messaging-operations/outbound-mail-phase-b1-live-acceptance-20260801.md"
)

for path in (STATE, ACCEPTANCE):
    assert path.is_file(), path

state = STATE.read_text(encoding="utf-8")
acceptance = ACCEPTANCE.read_text(encoding="utf-8")

for value in (
    "Last reconciled: 2026-08-01 19:00 UTC",
    "Phase B1 activation attempts: **2**",
    "latest Phase B1 attempt outcome: **successful**",
    "Phase B1 activation completed successfully: **yes**",
    "B1 runtime overlay currently installed: **yes**",
    "production HMAC secret currently installed: **yes; root-owned and not disclosed**",
    "preparation API enabled: **yes; loopback only**",
    "external delivery enabled: **no**",
    "live sender identities: **zero**",
    "ready delivery providers: **zero**",
    "production mail delivery: **no**",
    "f1f65571902c7f377c6a7ca9c52f634973a7635a",
    "/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1/20260801T190027Z",
    "Phase B1 is accepted as live on the Edge1 loopback boundary",
):
    assert value in state, value

for value in (
    "Host: `edge1.ww.cx`",
    "authenticated SSH as `wwadmin`",
    "bounded activation through `sudo` as `root`",
    "f1f65571902c7f377c6a7ca9c52f634973a7635a",
    "/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1/20260801T190027Z",
    "PHASE_B1_VALIDATION=PASS",
    "exactly `127.0.0.1:8104`",
    "unsigned preparation API response: HTTP `401`",
    "send endpoint response: HTTP `403`",
    "owner=root:root mode=0600",
    "temporary_secret_sources=0",
    "Every file listed in the evidence manifest passed",
    "No message was sent",
    "B2 reverse proxy or certificate installation",
    "external mail delivery or production message sending",
):
    assert value in acceptance, value

for prohibited in (
    "WWCX_MAIL_GATEWAY_TOKEN=",
    "X-WWCX-Signature:",
    "Bearer ",
    "BEGIN PRIVATE KEY",
):
    assert prohibited not in state, prohibited
    assert prohibited not in acceptance, prohibited

print("Outbound mail Phase B1 live acceptance validation passed")
print("Loopback preparation authentication is recorded as active")
print("External delivery, providers, senders, B2, DNS, and firewall remain inactive")
