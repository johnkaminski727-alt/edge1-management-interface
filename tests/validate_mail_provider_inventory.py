#!/usr/bin/env python3
"""Validate the durable mail-provider snapshot against canonical mail config."""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "config" / "messaging" / "mail-provider-inventory.json"
INBOUND_PATH = ROOT / "config" / "messaging" / "inbound-mail-hub.json"
IDENTITIES_PATH = ROOT / "config" / "messaging" / "mail-identities.json"
OUTBOUND_PATH = ROOT / "config" / "messaging" / "outbound-mail-gateway.json"
DOC_PATH = ROOT / "docs" / "messaging" / "mail-provider-inventory.md"

inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
inbound = json.loads(INBOUND_PATH.read_text(encoding="utf-8"))
identities = json.loads(IDENTITIES_PATH.read_text(encoding="utf-8"))
outbound = json.loads(OUTBOUND_PATH.read_text(encoding="utf-8"))

assert inventory["contract"] == "wwcx.mail-provider-inventory.v1"
assert inventory["production_changes_authorized"] is False
assert inventory["source"]["workflow_run_id"] == 30685903870
assert inventory["source"]["artifact_id"] == 8813887895
assert len(inventory["source"]["artifact_sha256"]) == 64
assert inventory["source"]["resolver_consensus"] is True
assert set(inventory["source"]["resolvers"]) == {"cloudflare", "google"}

expected_domains = {
    "ww.cx",
    "creekco.ca",
    "spiritcreekgardens.com",
    "scgardens.ca",
    "omegafx.com",
}
assert set(inventory["domains"]) == expected_domains
assert set(inbound["domains"]) == expected_domains
assert set(identities["domains"]) == expected_domains

canonical = inventory["canonical_internal_addresses"]
assert canonical["private_john_delivery_mailbox"] == "john-inbox@ww.cx"
assert canonical["shared_role_delivery_mailbox"] == "maildesk@ww.cx"
assert canonical["system_no_reply_sender"] == "noreply@ww.cx"
assert canonical["private_john_delivery_mailbox"] == identities["mailboxes"]["private_john"]["address"]
assert canonical["shared_role_delivery_mailbox"] == identities["mailboxes"]["shared_role"]["address"]
assert canonical["system_no_reply_sender"] == identities["system_senders"]["noreply"]["address"]

expected_provider_families = {
    "ww.cx": "namecheap_private_email",
    "creekco.ca": "namecheap_shared_hosting",
    "spiritcreekgardens.com": "no_published_mx_observed",
    "scgardens.ca": "namecheap_shared_hosting",
    "omegafx.com": "namecheap_shared_hosting",
}
for domain, provider_family in expected_provider_families.items():
    item = inventory["domains"][domain]
    assert item["provider_family"] == provider_family
    assert item["provider_confidence"] == "high"
    assert item["configured_route_count"] > 0

assert inventory["domains"]["ww.cx"]["mx"] == [
    "10 mx1.privateemail.com",
    "20 mx2.privateemail.com",
]
assert inventory["domains"]["ww.cx"]["dmarc"] == []
assert inventory["domains"]["spiritcreekgardens.com"]["mx"] == []
assert inventory["domains"]["spiritcreekgardens.com"]["spf"] == []
assert inventory["domains"]["spiritcreekgardens.com"]["dmarc"] == []
assert inventory["domains"]["spiritcreekgardens.com"]["delivery_status"] == "not_ready_no_mx"

routes = inbound["routing"]["routes"]
assert len(routes) == 37
for domain in expected_domains:
    configured_count = sum(1 for address in routes if address.endswith("@" + domain))
    assert configured_count == inventory["domains"][domain]["configured_route_count"]

private_destination = canonical["private_john_delivery_mailbox"]
shared_destination = canonical["shared_role_delivery_mailbox"]
assert private_destination != shared_destination
assert sum(1 for address in routes if address.startswith("john@")) == 5
assert all(
    route["destination"] == private_destination
    for address, route in routes.items()
    if address.startswith("john@")
)
assert all(
    route["destination"] == shared_destination
    for address, route in routes.items()
    if not address.startswith("john@")
)
assert private_destination not in routes
assert shared_destination not in routes
assert canonical["system_no_reply_sender"] not in routes

creekco = inventory["domains"]["creekco.ca"]
verified = set(creekco["verified_round_trip_addresses"])
observed_unregistered = set(creekco["observed_but_unregistered_addresses"])
configured_unverified = set(creekco["configured_but_unverified_addresses"])
assert creekco["configured_route_count"] == 13
assert creekco["registry_reconciliation_date"] == "2026-08-01"
assert verified == {
    "abuse@creekco.ca",
    "accessibility@creekco.ca",
    "contact@creekco.ca",
    "noc@creekco.ca",
    "privacy@creekco.ca",
    "regulatory@creekco.ca",
}
assert observed_unregistered == set()
assert verified.issubset(routes)
assert configured_unverified.issubset(routes)

mapping = identities["sender_selection"]["recipient_to_sender"]
profiles = identities["sender_profiles"]
for address, profile_key in {
    "accessibility@creekco.ca": "creekco-accessibility",
    "noc@creekco.ca": "creekco-noc",
}.items():
    assert routes[address]["destination"] == shared_destination
    assert mapping[address] == address
    assert profiles[profile_key]["address"] == address
    assert profiles[profile_key]["status"] == "verified_operational"
    assert profiles[profile_key]["outbound_enabled"] is False

assert inbound["enabled"] is False
assert inbound["deployment_authorized"] is False
assert inbound["production_routing_authorized"] is False
assert identities["outbound_activation_authorized"] is False
assert identities["sender_selection"]["live_sender_allowlist"] == []
assert outbound["enabled"] is False
assert outbound["deployment_authorized"] is False
assert outbound["external_delivery_authorized"] is False
assert outbound["admin"]["send_endpoint_enabled"] is False

activation = inventory["activation_boundary"]
assert activation
assert all(value is False for value in activation.values())
assert inventory["gaps"]
assert not any("not yet registered" in gap for gap in inventory["gaps"])

assert DOC_PATH.is_file()
document = DOC_PATH.read_text(encoding="utf-8")
for token in (
    "john-inbox@ww.cx",
    "maildesk@ww.cx",
    "noreply@ww.cx",
    "Namecheap Private Email",
    "Namecheap shared hosting",
    "spiritcreekgardens.com",
    "accessibility@creekco.ca",
    "noc@creekco.ca",
    "reconciled into the 37-route registry",
    "No DMARC policy should be tightened",
):
    assert token in document, token

print("Mail provider inventory validation passed")
print("Five domains reconciled against the 37-route inbound and identity configuration")
print("CreekCo accessibility and NOC evidence now matches the canonical registry")
print("All mailbox, DNS, routing, and outbound activation gates remain disabled")
