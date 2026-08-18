#!/usr/bin/env python3
"""Cross-check canonical Mail Room domains, identities, routes, and provider inventory.

The identity registry is the canonical configured domain set. Other configuration
may intentionally carry domain-specific operational data, but it must not silently
drift from that canonical set. This validator performs no external or production
changes.
"""

from __future__ import annotations

from typing import Any


CONTRACT = "wwcx.mail-config-consistency.v1"


class MailConfigConsistencyError(ValueError):
    """Raised when Mail Room configuration registries disagree."""


def _domain(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MailConfigConsistencyError(f"{label} must be non-empty text")
    normalized = value.strip().casefold()
    if normalized != value or "." not in normalized or "@" in normalized:
        raise MailConfigConsistencyError(f"{label} is not a normalized domain")
    return normalized


def _address_domain(value: Any, label: str) -> str:
    if not isinstance(value, str) or value.count("@") != 1:
        raise MailConfigConsistencyError(f"{label} is not an email address")
    local, domain = value.casefold().rsplit("@", 1)
    if not local or not domain or "." not in domain:
        raise MailConfigConsistencyError(f"{label} is not an email address")
    return domain


def validate(
    identities: dict[str, Any],
    inbound: dict[str, Any],
    outbound_policy: dict[str, Any],
    provider_inventory: dict[str, Any],
) -> dict[str, Any]:
    if identities.get("contract") != "wwcx.mail-identities.v2":
        raise MailConfigConsistencyError("unsupported identity registry")
    if inbound.get("contract") != "wwcx.inbound-mail-hub.v2":
        raise MailConfigConsistencyError("unsupported inbound hub")
    if outbound_policy.get("contract") != "wwcx.outbound-mail-policy.v1":
        raise MailConfigConsistencyError("unsupported outbound policy")
    if provider_inventory.get("contract") != "wwcx.mail-provider-inventory.v1":
        raise MailConfigConsistencyError("unsupported provider inventory")

    canonical = {_domain(item, "identity domain") for item in identities["domains"]}
    inbound_domains = {_domain(item, "inbound domain") for item in inbound["domains"]}
    outbound_domains = {
        _domain(item, "outbound allowed domain")
        for item in outbound_policy["delivery"]["allowed_from_domains"]
    }
    provider_domains = {
        _domain(item, "provider inventory domain")
        for item in provider_inventory["domains"]
    }

    mismatches: dict[str, dict[str, list[str]]] = {}
    for name, values in (
        ("inbound", inbound_domains),
        ("outbound", outbound_domains),
        ("provider_inventory", provider_domains),
    ):
        missing = sorted(canonical - values)
        unexpected = sorted(values - canonical)
        if missing or unexpected:
            mismatches[name] = {"missing": missing, "unexpected": unexpected}

    address_errors: list[str] = []
    for recipient, route in inbound["routing"]["routes"].items():
        domain = _address_domain(recipient, f"inbound route {recipient}")
        if domain not in canonical:
            address_errors.append(f"inbound route outside canonical domains: {recipient}")
        destination = route.get("destination")
        if route.get("destination_type") == "mailbox":
            destination_domain = _address_domain(
                destination, f"inbound route destination {recipient}"
            )
            if destination_domain not in canonical:
                address_errors.append(
                    f"inbound mailbox destination outside canonical domains: {destination}"
                )

    for recipient, sender in identities["sender_selection"]["recipient_to_sender"].items():
        if _address_domain(recipient, f"sender map recipient {recipient}") not in canonical:
            address_errors.append(f"sender-map recipient outside canonical domains: {recipient}")
        if _address_domain(sender, f"sender map sender {sender}") not in canonical:
            address_errors.append(f"sender-map sender outside canonical domains: {sender}")

    provider_internal = provider_inventory["canonical_internal_addresses"]
    identity_internal = {
        "private_john_delivery_mailbox": identities["mailboxes"]["private_john"]["address"],
        "shared_role_delivery_mailbox": identities["mailboxes"]["shared_role"]["address"],
        "system_no_reply_sender": identities["system_senders"]["noreply"]["address"],
    }
    internal_mismatches = {
        key: {"identity_registry": identity_internal[key], "provider_inventory": provider_internal.get(key)}
        for key in identity_internal
        if provider_internal.get(key) != identity_internal[key]
    }

    errors: list[str] = []
    if mismatches:
        errors.append("managed domain registries disagree")
    errors.extend(address_errors)
    if internal_mismatches:
        errors.append("canonical internal addresses disagree")
    if errors:
        raise MailConfigConsistencyError("; ".join(errors))

    return {
        "contract": CONTRACT,
        "consistent": True,
        "canonical_source": "config/messaging/mail-identities.json",
        "domains": sorted(canonical),
        "domain_count": len(canonical),
        "inbound_route_count": len(inbound["routing"]["routes"]),
        "sender_map_count": len(identities["sender_selection"]["recipient_to_sender"]),
        "internal_addresses": identity_internal,
    }
