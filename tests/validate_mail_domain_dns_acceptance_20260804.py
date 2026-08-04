#!/usr/bin/env python3
"""Validate the 2026-08-04 five-domain DNS acceptance record."""

from __future__ import annotations

import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / "records/messaging/dns-inventories/mail-domain-dns-acceptance-20260804.json"
CANONICAL = ROOT / "config/messaging/mail-provider-inventory.json"
OUTBOUND = ROOT / "config/messaging/outbound-mail-gateway.json"
IDENTITIES = ROOT / "config/messaging/mail-identities.json"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized(values: list[str]) -> list[str]:
    return sorted(values, key=lambda value: (int(value.split()[0]) if value.split()[0].isdigit() else 0, value))


acceptance = load(ACCEPTANCE)
canonical = load(CANONICAL)
outbound = load(OUTBOUND)
identities = load(IDENTITIES)

check(acceptance["contract"] == "wwcx.mail-domain-dns-acceptance.v1", "acceptance contract mismatch")
check(acceptance["read_only"] is True, "DNS acceptance must remain read-only")
check(acceptance["observed_at"] == "2026-08-04T00:31:11+00:00", "observation timestamp mismatch")
check(acceptance["source"]["workflow_run_id"] == 30865819181, "workflow run mismatch")
check(acceptance["source"]["artifact_id"] == 8876043654, "artifact ID mismatch")
check(acceptance["source"]["artifact_sha256"] == "002a11bab88c2c2d71de24ca94069650f32bd656356ab264c6e0f92d0329acd2", "artifact digest mismatch")
check(set(acceptance["source"]["resolvers"]) == {"cloudflare", "google"}, "resolver set mismatch")
check(acceptance["source"]["resolver_consensus"] is True, "source resolver consensus failed")

check(set(acceptance["domains"]) == set(canonical["domains"]), "managed domain set mismatch")
for domain, current in acceptance["domains"].items():
    expected = canonical["domains"][domain]
    check(current["provider_family"] == expected["provider_family"], f"{domain} provider family changed")
    check(current["provider_confidence"] == expected["provider_confidence"], f"{domain} provider confidence changed")
    check(normalized(current["mx"]) == normalized(expected["mx"]), f"{domain} MX changed")
    check(sorted(current["spf"]) == sorted(expected["spf"]), f"{domain} SPF changed")
    check(sorted(current["dmarc"]) == sorted(expected["dmarc"]), f"{domain} DMARC changed")
    check(sorted(current["authoritative_nameservers"]) == sorted(expected["authoritative_nameservers"]), f"{domain} nameservers changed")
    check(current["resolver_consensus"] is True, f"{domain} resolver consensus failed")

assessment = acceptance["assessment"]
check(assessment["matches_accepted_20260801_snapshot"] is True, "snapshot match marker changed")
check(assessment["wwcx_dmarc_published"] is False, "WW.CX DMARC was incorrectly reported present")
check(assessment["spiritcreekgardens_mail_ready"] is False, "Spirit Creek Gardens was incorrectly reported mail-ready")
check(assessment["dns_changes_authorized"] is False, "DNS change authorization appeared")
check(assessment["provider_or_sender_activated"] is False, "provider or sender activation appeared")
check(assessment["message_sent"] is False, "message activity appeared")

wwcx = acceptance["domains"]["ww.cx"]
check(wwcx["mx"] == ["10 mx1.privateemail.com", "20 mx2.privateemail.com"], "WW.CX MX mismatch")
check(wwcx["spf"] == ["v=spf1 include:spf.privateemail.com ~all"], "WW.CX SPF mismatch")
check(wwcx["dmarc"] == [], "WW.CX DMARC gap disappeared")

spirit = acceptance["domains"]["spiritcreekgardens.com"]
check(spirit["mx"] == [], "Spirit Creek Gardens MX unexpectedly appeared")
check(spirit["spf"] == [], "Spirit Creek Gardens SPF unexpectedly appeared")
check(spirit["dmarc"] == [], "Spirit Creek Gardens DMARC unexpectedly appeared")

for domain in ("creekco.ca", "scgardens.ca", "omegafx.com"):
    item = acceptance["domains"][domain]
    check(item["dmarc"] == ["v=DMARC1; p=none;"], f"{domain} DMARC monitoring policy changed")
    check(item["provider_family"] == "namecheap_shared_hosting", f"{domain} provider inference changed")

check(outbound["enabled"] is False, "outbound gateway became enabled")
check(outbound["external_delivery_authorized"] is False, "external delivery became authorized")
check(outbound["admin"]["send_endpoint_enabled"] is False, "send endpoint became enabled")
check(identities["outbound_activation_authorized"] is False, "sender activation became authorized")
check(identities["sender_selection"]["live_sender_allowlist"] == [], "live sender allowlist is not empty")

print("Mail domain DNS acceptance validation passed")
print("August 4 resolver consensus matches the accepted August 1 snapshot")
print("WW.CX still lacks DMARC and Spirit Creek Gardens still lacks MX, SPF, and DMARC")
print("No DNS, provider, sender, delivery, or message authorization changed")
