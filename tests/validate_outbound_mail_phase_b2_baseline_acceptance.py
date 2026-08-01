#!/usr/bin/env python3
"""Validate the accepted non-mutating Phase B2 baseline record."""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / ".agent/outbound-mail-b2-readiness.md"
ACCEPTANCE = ROOT / "docs/messaging-operations/outbound-mail-phase-b2-baseline-acceptance-20260801.md"
AUDIT = ROOT / "tools/messaging/outbound_mail_phase_b2_readiness_audit.sh"

for path in (STATE, ACCEPTANCE, AUDIT):
    assert path.is_file(), path

state = STATE.read_text(encoding="utf-8")
acceptance = ACCEPTANCE.read_text(encoding="utf-8")
audit = AUDIT.read_text(encoding="utf-8")

required_facts = (
    "2026-08-01T19:28:18Z",
    "03f8a67b17b258459ee71b6a2a7a31187987506c",
    "/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-readiness/20260801T192818Z",
    "awaiting_explicit_b2_parameters",
    "unsigned preparation API status: HTTP `401`",
    "send probe: HTTP `403`",
)
for value in required_facts:
    assert value in state or value in acceptance, value

non_mutation_markers = (
    "hmac_secret_read=no",
    "certificate_private_key_read=no",
    "candidate_config_written_to_evidence_only=yes",
    "proxy_config_installed=no",
    "proxy_service_reloaded=no",
    "certificate_generated=no",
    "dns_modified=no",
    "firewall_modified=no",
    "public_listener_added=no",
    "website_bridge_enabled=no",
    "provider_or_sender_enabled=no",
    "message_sent=no",
)
for value in non_mutation_markers:
    assert value in acceptance, value
    spaced = value.replace("=", " ", 1)
    assert spaced in audit, spaced

for value in (
    "exact API hostname",
    "exact client source `/32` or `/128`",
    "certificate full-chain path",
    "certificate private-key path",
    "does not authorize certificate access",
    "does not mean the proxy is ready for installation",
    "A generic continuation instruction does not authorize",
):
    assert value in acceptance, value

for value in (
    "## Historical baseline authorization record",
    "proxy installation or reload authorized: **no**",
    "DNS change authorized: **no**",
    "firewall change authorized: **no**",
    "production message authorized: **no**",
    "A generic `Continue` does not authorize",
    "## Authorization received",
    "`I am authorizing all work.`",
    "proxy installation or reload: **authorized only after exact proposal validation and rollback review**",
    "production message: **not defined or sent**",
):
    assert value in state, value

assert "ready_for_explicit_b2_authorization" not in acceptance
assert "proxy_config_installed=yes" not in acceptance
assert "message_sent=yes" not in acceptance
assert "WWCX_MAIL_GATEWAY_TOKEN=" not in acceptance
assert "BEGIN PRIVATE KEY" not in acceptance

print("Outbound mail Phase B2 baseline acceptance validation passed")
print("The 19:28 UTC baseline remains non-mutating and historically immutable")
print("Later authorization is conditional on exact parameters, rollback, evidence, and credential secrecy")
