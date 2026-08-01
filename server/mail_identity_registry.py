#!/usr/bin/env python3
"""Validation and automatic sender selection for WW.CX mail identities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CONTRACT = "wwcx.mail-identities.v2"
SELECTION_STRATEGY = "system_flag_then_original_recipient_then_identity_hint_then_default"


class IdentityRegistryError(RuntimeError):
    """Base identity-registry failure."""


class IdentityConfigurationError(IdentityRegistryError):
    """Raised when the identity registry is invalid."""


class IdentitySelectionError(IdentityRegistryError):
    """Raised when the gateway cannot safely resolve a sender."""


@dataclass(frozen=True)
class SenderSelection:
    address: str
    identity_key: str | None
    reason: str
    submitted_from_present: bool
    from_address_replaced: bool
    live_enabled: bool
    reply_to: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "identity_key": self.identity_key,
            "reason": self.reason,
            "submitted_from_present": self.submitted_from_present,
            "from_address_replaced": self.from_address_replaced,
            "live_enabled": self.live_enabled,
            "reply_to": self.reply_to,
        }


def _require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise IdentityConfigurationError(
            f"{label} keys invalid; missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IdentityConfigurationError(f"{label} must be non-empty text")
    return value.strip()


def _require_bool(value: Any, label: str) -> None:
    if not isinstance(value, bool):
        raise IdentityConfigurationError(f"{label} must be boolean")


def normalize_address(value: Any, label: str = "address") -> str:
    address = _require_text(value, label).casefold()
    if "\r" in address or "\n" in address or address.count("@") != 1:
        raise IdentityConfigurationError(f"{label} is invalid")
    local, domain = address.rsplit("@", 1)
    if not local or not domain or "." not in domain:
        raise IdentityConfigurationError(f"{label} is invalid")
    return address


def _optional_address(value: Any, label: str) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return normalize_address(value, label)
    except IdentityConfigurationError as exc:
        raise IdentitySelectionError(str(exc)) from exc


def validate_registry(registry: dict[str, Any]) -> None:
    if not isinstance(registry, dict):
        raise IdentityConfigurationError("identity registry must be an object")
    _require_exact_keys(
        registry,
        {
            "contract",
            "outbound_activation_authorized",
            "mailboxes",
            "system_senders",
            "domains",
            "sender_profiles",
            "sender_selection",
            "rules",
        },
        "identity registry",
    )
    if registry["contract"] != CONTRACT:
        raise IdentityConfigurationError("unsupported identity registry contract")
    _require_bool(
        registry["outbound_activation_authorized"],
        "outbound_activation_authorized",
    )

    domains = registry["domains"]
    if not isinstance(domains, dict) or not domains:
        raise IdentityConfigurationError("domains must be a non-empty object")
    normalized_domains: set[str] = set()
    for domain, definition in domains.items():
        normalized_domain = _require_text(domain, "domain").casefold()
        if normalized_domain != domain or "." not in normalized_domain:
            raise IdentityConfigurationError("domain keys must be normalized lowercase domains")
        if normalized_domain in normalized_domains:
            raise IdentityConfigurationError("domains must be unique")
        normalized_domains.add(normalized_domain)
        if not isinstance(definition, dict):
            raise IdentityConfigurationError(f"domain {domain} must be an object")
        _require_exact_keys(
            definition,
            {"legal_name", "operating_name", "purpose", "identity_role", "preferred_outbound"},
            f"domain.{domain}",
        )
        for key in ("legal_name", "operating_name", "purpose", "identity_role"):
            _require_text(definition[key], f"domain.{domain}.{key}")
        _require_bool(definition["preferred_outbound"], f"domain.{domain}.preferred_outbound")

    mailboxes = registry["mailboxes"]
    if not isinstance(mailboxes, dict):
        raise IdentityConfigurationError("mailboxes must be an object")
    _require_exact_keys(mailboxes, {"private_john", "shared_role"}, "mailboxes")
    mailbox_addresses: dict[str, str] = {}
    for name, definition in mailboxes.items():
        if not isinstance(definition, dict):
            raise IdentityConfigurationError(f"mailbox {name} must be an object")
        _require_exact_keys(
            definition,
            {"address", "access", "purpose", "accepts_direct_public_use"},
            f"mailbox.{name}",
        )
        address = normalize_address(definition["address"], f"mailbox.{name}.address")
        if address.rsplit("@", 1)[1] not in normalized_domains:
            raise IdentityConfigurationError(f"mailbox {name} is outside managed domains")
        mailbox_addresses[name] = address
        _require_text(definition["access"], f"mailbox.{name}.access")
        _require_text(definition["purpose"], f"mailbox.{name}.purpose")
        _require_bool(
            definition["accepts_direct_public_use"],
            f"mailbox.{name}.accepts_direct_public_use",
        )
    if len(set(mailbox_addresses.values())) != len(mailbox_addresses):
        raise IdentityConfigurationError("private and shared delivery mailboxes must be distinct")

    system_senders = registry["system_senders"]
    if not isinstance(system_senders, dict):
        raise IdentityConfigurationError("system_senders must be an object")
    _require_exact_keys(system_senders, {"noreply"}, "system_senders")
    noreply = system_senders["noreply"]
    if not isinstance(noreply, dict):
        raise IdentityConfigurationError("system_senders.noreply must be an object")
    _require_exact_keys(
        noreply,
        {"address", "purpose", "reply_policy", "outbound_enabled"},
        "system_senders.noreply",
    )
    system_address = normalize_address(noreply["address"], "system_senders.noreply.address")
    if system_address.rsplit("@", 1)[1] not in normalized_domains:
        raise IdentityConfigurationError("system sender is outside managed domains")
    _require_text(noreply["purpose"], "system_senders.noreply.purpose")
    if noreply["reply_policy"] != "no_reply":
        raise IdentityConfigurationError("noreply sender must use no_reply policy")
    _require_bool(noreply["outbound_enabled"], "system_senders.noreply.outbound_enabled")
    if system_address in mailbox_addresses.values():
        raise IdentityConfigurationError("noreply address cannot be a delivery mailbox")

    profiles = registry["sender_profiles"]
    if not isinstance(profiles, dict) or not profiles:
        raise IdentityConfigurationError("sender_profiles must be a non-empty object")
    for key, profile in profiles.items():
        _require_text(key, "sender profile key")
        if not isinstance(profile, dict):
            raise IdentityConfigurationError(f"sender profile {key} must be an object")
        _require_exact_keys(
            profile,
            {
                "address",
                "display_name",
                "organization",
                "use_for",
                "address_class",
                "status",
                "outbound_enabled",
            },
            f"sender_profile.{key}",
        )
        address = normalize_address(profile["address"], f"sender_profile.{key}.address")
        if address.rsplit("@", 1)[1] not in normalized_domains:
            raise IdentityConfigurationError(f"sender profile {key} is outside managed domains")
        for field in ("display_name", "organization", "use_for", "address_class", "status"):
            _require_text(profile[field], f"sender_profile.{key}.{field}")
        _require_bool(profile["outbound_enabled"], f"sender_profile.{key}.outbound_enabled")

    selection = registry["sender_selection"]
    if not isinstance(selection, dict):
        raise IdentityConfigurationError("sender_selection must be an object")
    _require_exact_keys(
        selection,
        {
            "enabled",
            "strategy",
            "allow_submitted_from_override",
            "default_sender",
            "system_sender",
            "reject_unknown_original_recipient",
            "live_sender_allowlist",
            "recipient_to_sender",
        },
        "sender_selection",
    )
    _require_bool(selection["enabled"], "sender_selection.enabled")
    if selection["strategy"] != SELECTION_STRATEGY:
        raise IdentityConfigurationError("unsupported sender-selection strategy")
    _require_bool(
        selection["allow_submitted_from_override"],
        "sender_selection.allow_submitted_from_override",
    )
    if selection["allow_submitted_from_override"]:
        raise IdentityConfigurationError("submitted From override must remain disabled")
    _require_bool(
        selection["reject_unknown_original_recipient"],
        "sender_selection.reject_unknown_original_recipient",
    )

    recipient_map = selection["recipient_to_sender"]
    if not isinstance(recipient_map, dict) or not recipient_map:
        raise IdentityConfigurationError("recipient_to_sender must be a non-empty object")
    normalized_map: dict[str, str] = {}
    for recipient, sender in recipient_map.items():
        normalized_recipient = normalize_address(recipient, "recipient_to_sender recipient")
        normalized_sender = normalize_address(sender, f"recipient_to_sender.{recipient}")
        if normalized_recipient != recipient or normalized_sender != sender:
            raise IdentityConfigurationError("recipient_to_sender entries must be normalized lowercase")
        if normalized_recipient.rsplit("@", 1)[1] not in normalized_domains:
            raise IdentityConfigurationError("recipient_to_sender recipient is outside managed domains")
        if normalized_sender.rsplit("@", 1)[1] not in normalized_domains:
            raise IdentityConfigurationError("recipient_to_sender sender is outside managed domains")
        normalized_map[normalized_recipient] = normalized_sender

    default_sender = normalize_address(selection["default_sender"], "sender_selection.default_sender")
    configured_system_sender = normalize_address(
        selection["system_sender"], "sender_selection.system_sender"
    )
    if configured_system_sender != system_address:
        raise IdentityConfigurationError("sender-selection system sender does not match registry")
    allowed_selection_addresses = set(normalized_map.values()) | {system_address}
    if default_sender not in allowed_selection_addresses:
        raise IdentityConfigurationError("default sender is not a registered sender identity")

    live_allowlist = selection["live_sender_allowlist"]
    if not isinstance(live_allowlist, list):
        raise IdentityConfigurationError("live_sender_allowlist must be a list")
    normalized_allowlist = [normalize_address(item, "live sender") for item in live_allowlist]
    if len(set(normalized_allowlist)) != len(normalized_allowlist):
        raise IdentityConfigurationError("live sender allowlist must be unique")
    if not set(normalized_allowlist).issubset(allowed_selection_addresses):
        raise IdentityConfigurationError("live sender allowlist contains an unknown identity")
    if registry["outbound_activation_authorized"] and not normalized_allowlist:
        raise IdentityConfigurationError("outbound activation requires at least one live sender")

    rules = registry["rules"]
    if not isinstance(rules, dict):
        raise IdentityConfigurationError("rules must be an object")
    _require_exact_keys(
        rules,
        {
            "reply_from_matching_identity",
            "allow_legacy_alias_as_outbound_sender",
            "require_sender_domain_alignment",
            "require_dkim_before_outbound_activation",
            "require_dmarc_review_before_outbound_activation",
            "private_john_addresses",
            "primary_work_address",
            "private_john_delivery_mailbox",
            "shared_role_delivery_mailbox",
            "system_sender",
            "require_distinct_private_and_role_destinations",
            "delivery_mailboxes_are_internal_only",
        },
        "rules",
    )
    for field in (
        "reply_from_matching_identity",
        "allow_legacy_alias_as_outbound_sender",
        "require_sender_domain_alignment",
        "require_dkim_before_outbound_activation",
        "require_dmarc_review_before_outbound_activation",
        "require_distinct_private_and_role_destinations",
        "delivery_mailboxes_are_internal_only",
    ):
        _require_bool(rules[field], f"rules.{field}")
    if not rules["reply_from_matching_identity"]:
        raise IdentityConfigurationError("reply-from-matching-identity must remain enabled")
    if not rules["require_distinct_private_and_role_destinations"]:
        raise IdentityConfigurationError("private and role destinations must remain distinct")
    if not rules["delivery_mailboxes_are_internal_only"]:
        raise IdentityConfigurationError("delivery mailboxes must remain internal-only identities")

    private_addresses = rules["private_john_addresses"]
    if not isinstance(private_addresses, list) or not private_addresses:
        raise IdentityConfigurationError("private_john_addresses must be a non-empty list")
    normalized_private = [normalize_address(item, "private John address") for item in private_addresses]
    if len(set(normalized_private)) != len(normalized_private):
        raise IdentityConfigurationError("private John addresses must be unique")
    if not set(normalized_private).issubset(normalized_map):
        raise IdentityConfigurationError("private John address is missing from sender mapping")
    for address in normalized_private:
        if normalized_map[address] != address:
            raise IdentityConfigurationError("private John identities must reply from themselves")

    primary_work = normalize_address(rules["primary_work_address"], "rules.primary_work_address")
    if primary_work not in normalized_private:
        raise IdentityConfigurationError("primary work address must remain private to John")
    if normalize_address(
        rules["private_john_delivery_mailbox"],
        "rules.private_john_delivery_mailbox",
    ) != mailbox_addresses["private_john"]:
        raise IdentityConfigurationError("private delivery mailbox rule does not match mailbox registry")
    if normalize_address(
        rules["shared_role_delivery_mailbox"],
        "rules.shared_role_delivery_mailbox",
    ) != mailbox_addresses["shared_role"]:
        raise IdentityConfigurationError("shared delivery mailbox rule does not match mailbox registry")
    if normalize_address(rules["system_sender"], "rules.system_sender") != system_address:
        raise IdentityConfigurationError("system sender rule does not match system registry")
    if mailbox_addresses["private_john"] in normalized_map:
        raise IdentityConfigurationError("private delivery mailbox must not be a public sender identity")
    if mailbox_addresses["shared_role"] in normalized_map:
        raise IdentityConfigurationError("shared delivery mailbox must not be a public sender identity")


def _profile_key_for_address(registry: dict[str, Any], address: str) -> str | None:
    for key, profile in registry["sender_profiles"].items():
        if profile["address"].casefold() == address:
            return key
    return None


def sender_options(registry: dict[str, Any]) -> list[dict[str, Any]]:
    validate_registry(registry)
    selection = registry["sender_selection"]
    live_allowlist = set(selection["live_sender_allowlist"])
    profile_by_address = {
        profile["address"]: (key, profile)
        for key, profile in registry["sender_profiles"].items()
    }
    addresses = sorted(set(selection["recipient_to_sender"].values()))
    addresses.append(selection["system_sender"])
    result: list[dict[str, Any]] = []
    for address in addresses:
        profile_item = profile_by_address.get(address)
        if profile_item:
            key, profile = profile_item
            display_name = profile["display_name"]
            organization = profile["organization"]
            address_class = profile["address_class"]
        else:
            key = None
            display_name = address
            organization = registry["domains"][address.rsplit("@", 1)[1]]["operating_name"]
            address_class = "mapped_role"
        result.append(
            {
                "key": key,
                "address": address,
                "display_name": display_name,
                "organization": organization,
                "address_class": address_class,
                "live_enabled": bool(
                    registry["outbound_activation_authorized"] and address in live_allowlist
                ),
            }
        )
    return result


def resolve_sender(registry: dict[str, Any], payload: dict[str, Any]) -> SenderSelection:
    validate_registry(registry)
    if not isinstance(payload, dict):
        raise IdentitySelectionError("message payload must be an object")
    selection = registry["sender_selection"]
    if not selection["enabled"]:
        raise IdentitySelectionError("automatic sender selection is disabled")

    submitted_from = _optional_address(payload.get("from_address"), "from_address")
    original_recipient = _optional_address(
        payload.get("original_recipient"), "original_recipient"
    )
    identity_hint_raw = str(payload.get("identity_hint", "")).strip()
    system_generated = payload.get("system_generated", False)
    if not isinstance(system_generated, bool):
        raise IdentitySelectionError("system_generated must be boolean")

    recipient_map = selection["recipient_to_sender"]
    profiles = registry["sender_profiles"]
    if system_generated:
        selected = selection["system_sender"]
        reason = "system_generated"
        identity_key = _profile_key_for_address(registry, selected)
    elif original_recipient:
        selected = recipient_map.get(original_recipient)
        if selected is None:
            if selection["reject_unknown_original_recipient"]:
                raise IdentitySelectionError("original recipient is not a registered mail identity")
            selected = selection["default_sender"]
            reason = "default_unknown_original_recipient"
        else:
            reason = "original_recipient"
        identity_key = _profile_key_for_address(registry, selected)
    elif identity_hint_raw:
        if identity_hint_raw in profiles:
            selected = profiles[identity_hint_raw]["address"]
            identity_key = identity_hint_raw
        else:
            hinted_address = _optional_address(identity_hint_raw, "identity_hint")
            assert hinted_address is not None
            allowed = set(recipient_map.values()) | {selection["system_sender"]}
            if hinted_address not in allowed:
                raise IdentitySelectionError("identity hint is not a registered sender identity")
            selected = hinted_address
            identity_key = _profile_key_for_address(registry, selected)
        reason = "identity_hint"
    else:
        selected = selection["default_sender"]
        identity_key = _profile_key_for_address(registry, selected)
        reason = "default_sender"

    live_enabled = bool(
        registry["outbound_activation_authorized"]
        and selected in set(selection["live_sender_allowlist"])
    )
    reply_to = None if selected == selection["system_sender"] else selected
    return SenderSelection(
        address=selected,
        identity_key=identity_key,
        reason=reason,
        submitted_from_present=submitted_from is not None,
        from_address_replaced=bool(submitted_from and submitted_from != selected),
        live_enabled=live_enabled,
        reply_to=reply_to,
    )


def status_payload(registry: dict[str, Any]) -> dict[str, Any]:
    validate_registry(registry)
    return {
        "contract": CONTRACT,
        "automatic_selection_enabled": registry["sender_selection"]["enabled"],
        "strategy": registry["sender_selection"]["strategy"],
        "allow_submitted_from_override": registry["sender_selection"][
            "allow_submitted_from_override"
        ],
        "default_sender": registry["sender_selection"]["default_sender"],
        "system_sender": registry["sender_selection"]["system_sender"],
        "private_delivery_mailbox": registry["mailboxes"]["private_john"]["address"],
        "shared_delivery_mailbox": registry["mailboxes"]["shared_role"]["address"],
        "outbound_activation_authorized": registry["outbound_activation_authorized"],
        "live_sender_count": len(registry["sender_selection"]["live_sender_allowlist"]),
        "identities": sender_options(registry),
    }
