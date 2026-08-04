#!/usr/bin/env python3
"""Offline readiness analysis for outbound-mail provider activation.

This tool reads only committed JSON configuration. It does not inspect runtime
credential values, query DNS or providers, change configuration, or send mail.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import datetime, timezone
from typing import Any

REPORT_CONTRACT = "wwcx.outbound-mail-phase-e-readiness.v1"
GATEWAY_CONTRACT = "wwcx.outbound-mail-gateway.v1"
POLICY_CONTRACT = "wwcx.outbound-mail-policy.v1"
IDENTITIES_CONTRACT = "wwcx.mail-identities.v2"
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,80}$")


class ReadinessError(RuntimeError):
    """Raised when an input cannot be analyzed safely."""


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReadinessError(f"unable to read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReadinessError(f"{path} must contain a JSON object")
    return value


def require_contract(value: dict[str, Any], expected: str, label: str) -> None:
    if value.get("contract") != expected:
        raise ReadinessError(f"{label} uses an unsupported contract")


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ReadinessError(f"{label} must be boolean")
    return value


def add_blocker(
    blockers: list[dict[str, str]],
    code: str,
    category: str,
    detail: str,
    required_action: str,
    approval_boundary: str,
) -> None:
    blockers.append(
        {
            "code": code,
            "category": category,
            "detail": detail,
            "required_action": required_action,
            "approval_boundary": approval_boundary,
        }
    )


def _provider_summary(gateway: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    provider = gateway.get("provider")
    if not isinstance(provider, dict):
        raise ReadinessError("gateway.provider must be an object")
    selected = provider.get("selected")
    profiles = provider.get("profiles")
    if not isinstance(selected, str) or not isinstance(profiles, dict) or selected not in profiles:
        raise ReadinessError("gateway provider selection is invalid")

    summaries: list[dict[str, Any]] = []
    credential_names: list[str] = []
    for name, raw_profile in profiles.items():
        if not isinstance(name, str) or not isinstance(raw_profile, dict):
            raise ReadinessError("gateway provider profile is invalid")
        provider_type = raw_profile.get("type")
        enabled = require_bool(raw_profile.get("enabled"), f"provider.{name}.enabled")
        if provider_type not in {"disabled", "smtp", "gmail_api", "webhook"}:
            raise ReadinessError(f"provider.{name}.type is unsupported")
        env_names = [
            str(value)
            for key, value in raw_profile.items()
            if key.endswith("_env") and isinstance(value, str)
        ]
        if any(not ENV_NAME_RE.fullmatch(value) for value in env_names):
            raise ReadinessError(f"provider.{name} contains an invalid environment-variable name")
        credential_names.extend(env_names)
        summaries.append(
            {
                "name": name,
                "type": provider_type,
                "selected": name == selected,
                "enabled": enabled,
                "adapter_implemented": provider_type in {"smtp", "disabled"},
                "credential_environment_names": sorted(env_names),
                "credential_values_inspected": False,
            }
        )
    return summaries, sorted(set(credential_names))


def analyze(
    gateway: dict[str, Any],
    policy: dict[str, Any],
    identities: dict[str, Any],
) -> dict[str, Any]:
    require_contract(gateway, GATEWAY_CONTRACT, "gateway")
    require_contract(policy, POLICY_CONTRACT, "policy")
    require_contract(identities, IDENTITIES_CONTRACT, "identities")

    provider_summaries, credential_names = _provider_summary(gateway)
    provider = gateway["provider"]
    selected_provider = str(provider["selected"])
    selected_profile = provider["profiles"][selected_provider]
    admin = gateway.get("admin")
    delivery = policy.get("delivery")
    organization = policy.get("organization")
    sender_selection = identities.get("sender_selection")
    sender_profiles = identities.get("sender_profiles")
    rules = identities.get("rules")
    if not all(
        isinstance(value, dict)
        for value in (admin, delivery, organization, sender_selection, sender_profiles, rules)
    ):
        raise ReadinessError("mail configuration contains an invalid object")

    live_sender_allowlist = sender_selection.get("live_sender_allowlist")
    if not isinstance(live_sender_allowlist, list) or not all(
        isinstance(item, str) for item in live_sender_allowlist
    ):
        raise ReadinessError("live sender allowlist must be a text list")

    enabled_sender_profiles: list[str] = []
    candidate_senders: list[dict[str, Any]] = []
    for key, profile in sender_profiles.items():
        if not isinstance(key, str) or not isinstance(profile, dict):
            raise ReadinessError("sender profile is invalid")
        address = profile.get("address")
        status = profile.get("status")
        enabled = require_bool(profile.get("outbound_enabled"), f"sender_profiles.{key}.outbound_enabled")
        if not isinstance(address, str) or not isinstance(status, str):
            raise ReadinessError(f"sender profile {key} is incomplete")
        if enabled:
            enabled_sender_profiles.append(address)
        candidate_senders.append(
            {
                "identity_key": key,
                "address": address,
                "status": status,
                "outbound_enabled": enabled,
                "allowlisted": address in live_sender_allowlist,
                "domain_authentication_verified": False,
                "provider_sender_capability_verified": False,
                "ready_for_pilot": False,
            }
        )

    blockers: list[dict[str, str]] = []
    if not require_bool(gateway.get("enabled"), "gateway.enabled"):
        add_blocker(blockers, "gateway_disabled", "gateway", "The gateway master gate is disabled.", "Enable only after all Phase E evidence is accepted.", "production_cutover")
    if not require_bool(gateway.get("deployment_authorized"), "gateway.deployment_authorized"):
        add_blocker(blockers, "gateway_deployment_not_authorized", "gateway", "Production gateway deployment is not authorized.", "Record explicit production deployment authorization.", "production_deployment")
    if not require_bool(gateway.get("external_delivery_authorized"), "gateway.external_delivery_authorized"):
        add_blocker(blockers, "external_delivery_not_authorized", "gateway", "External message delivery is not authorized.", "Obtain explicit external-delivery authorization for a bounded pilot.", "production_message_traffic")
    if not require_bool(admin.get("send_endpoint_enabled"), "admin.send_endpoint_enabled"):
        add_blocker(blockers, "send_endpoint_disabled", "gateway", "The send endpoint is disabled.", "Enable only in the approved pilot runtime overlay.", "production_cutover")
    if selected_provider == "none" or selected_profile.get("type") == "disabled":
        add_blocker(blockers, "provider_not_selected", "provider", "No delivery provider is selected.", "Select one reviewed provider profile; SMTP is the only implemented live adapter.", "provider_terms_and_credentials")
    if not require_bool(selected_profile.get("enabled"), f"provider.{selected_provider}.enabled"):
        add_blocker(blockers, "selected_provider_disabled", "provider", "The selected provider profile is disabled.", "Enable the selected profile only in a reviewed runtime overlay.", "provider_credentials")

    if not require_bool(policy.get("enabled"), "policy.enabled"):
        add_blocker(blockers, "policy_disabled", "policy", "Outbound policy enforcement is disabled for delivery.", "Enable the policy only with the pilot activation.", "production_cutover")
    if not require_bool(policy.get("deployment_authorized"), "policy.deployment_authorized"):
        add_blocker(blockers, "policy_deployment_not_authorized", "policy", "Policy deployment is not authorized.", "Record explicit policy deployment authorization.", "production_deployment")
    if not require_bool(policy.get("smtp_cutover_authorized"), "policy.smtp_cutover_authorized"):
        add_blocker(blockers, "smtp_cutover_not_authorized", "policy", "SMTP cutover is not authorized.", "Authorize the exact provider, sender, envelope and pilot recipient.", "smtp_cutover")
    if delivery.get("provider") == "disabled":
        add_blocker(blockers, "policy_provider_disabled", "policy", "Policy delivery provider remains disabled.", "Align the runtime policy with the approved provider.", "production_cutover")
    if require_bool(delivery.get("allow_external_submission"), "delivery.allow_external_submission") is not True:
        add_blocker(blockers, "external_submission_disabled", "policy", "Policy forbids external submission.", "Enable only for the bounded pilot.", "production_message_traffic")
    if require_bool(delivery.get("allow_live_delivery"), "delivery.allow_live_delivery") is not True:
        add_blocker(blockers, "live_delivery_disabled", "policy", "Policy forbids live delivery.", "Enable only for the bounded pilot.", "production_message_traffic")
    if organization.get("mailing_address") in {None, "", "CONFIGURE_AT_DEPLOYMENT"}:
        add_blocker(blockers, "mailing_address_unconfigured", "content_policy", "The controlled footer mailing address is not configured.", "Set and review the correct organization mailing address in the runtime policy.", "production_configuration")

    if not require_bool(identities.get("outbound_activation_authorized"), "identities.outbound_activation_authorized"):
        add_blocker(blockers, "identity_activation_not_authorized", "sender", "Global outbound sender activation is not authorized.", "Authorize one named pilot sender only after provider and domain evidence passes.", "sender_activation")
    if not live_sender_allowlist:
        add_blocker(blockers, "live_sender_allowlist_empty", "sender", "No sender is allowlisted for live delivery.", "Add exactly one verified pilot sender to the runtime allowlist.", "sender_activation")
    if not enabled_sender_profiles:
        add_blocker(blockers, "no_sender_profile_enabled", "sender", "Every sender profile remains live-disabled.", "Enable exactly one verified pilot profile in the runtime overlay.", "sender_activation")
    if require_bool(rules.get("require_dkim_before_outbound_activation"), "rules.require_dkim_before_outbound_activation"):
        add_blocker(blockers, "dkim_evidence_required", "domain_authentication", "The identity policy requires DKIM evidence before activation.", "Capture selector, signing and alignment evidence for the pilot sender domain.", "dns_and_provider_configuration")
    if require_bool(rules.get("require_dmarc_review_before_outbound_activation"), "rules.require_dmarc_review_before_outbound_activation"):
        add_blocker(blockers, "dmarc_review_required", "domain_authentication", "The identity policy requires DMARC review before activation.", "Review current DMARC policy and aggregate-report implications.", "dns_policy")

    for code, detail, action, boundary in [
        ("provider_inventory_incomplete", "A complete provider-side mailbox, alias, sender-capability and DKIM inventory is not attached to this analysis.", "Complete and accept the provider-object reconciliation.", "provider_access"),
        ("provider_terms_unreviewed", "Provider commercial terms, limits and acceptable-use conditions are not evidenced.", "Review and accept the selected provider terms and limits.", "commercial_terms"),
        ("runtime_credentials_absent", "Provider credentials are intentionally not inspected or installed by this tool.", "Install credentials through an approved secret path after authorization.", "provider_credentials"),
        ("return_path_undefined", "The pilot envelope sender and return-path are not evidenced.", "Define an aligned return-path and bounce domain.", "dns_and_provider_configuration"),
        ("spf_alignment_unverified", "SPF authorization and alignment for the intended provider are not evidenced.", "Verify or stage the exact SPF change without disrupting existing senders.", "dns_change"),
        ("bounce_ingestion_undefined", "Bounce and delivery-status ingestion are not evidenced.", "Implement bounded bounce classification and suppression handling.", "production_integration"),
        ("complaint_suppression_undefined", "Complaint and suppression handling are not evidenced.", "Define provider complaint ingestion and sender suppression rules.", "production_integration"),
        ("pilot_recipient_not_authorized", "No controlled pilot recipient is authorized in the committed state.", "Authorize one WW.CX-controlled test inbox for the first message.", "production_message_traffic"),
        ("production_message_not_authorized", "No production message is authorized.", "Authorize one exact pilot message only after every readiness gate passes.", "production_message_traffic"),
    ]:
        add_blocker(blockers, code, "evidence", detail, action, boundary)

    live_gate_values = {
        "gateway_enabled": gateway["enabled"],
        "gateway_deployment_authorized": gateway["deployment_authorized"],
        "external_delivery_authorized": gateway["external_delivery_authorized"],
        "send_endpoint_enabled": admin["send_endpoint_enabled"],
        "policy_enabled": policy["enabled"],
        "policy_deployment_authorized": policy["deployment_authorized"],
        "smtp_cutover_authorized": policy["smtp_cutover_authorized"],
        "allow_external_submission": delivery["allow_external_submission"],
        "allow_live_delivery": delivery["allow_live_delivery"],
        "identity_activation_authorized": identities["outbound_activation_authorized"],
    }
    any_live_gate = any(value is True for value in live_gate_values.values())
    all_live_gates = all(value is True for value in live_gate_values.values())
    any_live_sender = bool(enabled_sender_profiles or live_sender_allowlist)
    unsafe_partial = (any_live_gate or any_live_sender) and not all_live_gates
    safe_disabled = not any_live_gate and not any_live_sender
    readiness_state = "unsafe_partial_activation" if unsafe_partial else "safe_disabled" if safe_disabled else "not_ready"

    return {
        "contract": REPORT_CONTRACT,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "readiness_state": readiness_state,
        "ready_for_provider_activation": len(blockers) == 0 and all_live_gates,
        "runtime_credentials_inspected": False,
        "network_or_dns_queries_performed": False,
        "configuration_modified": False,
        "message_prepared": False,
        "message_sent": False,
        "selected_provider": selected_provider,
        "first_implemented_delivery_adapter": "smtp_submission",
        "provider_profiles": provider_summaries,
        "credential_environment_names": credential_names,
        "live_gates": live_gate_values,
        "live_sender_allowlist": list(live_sender_allowlist),
        "enabled_sender_profiles": sorted(enabled_sender_profiles),
        "candidate_senders": candidate_senders,
        "blocker_count": len(blockers),
        "blockers": blockers,
    }


def parse_args() -> argparse.Namespace:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", type=pathlib.Path, default=repo_root / "config/messaging/outbound-mail-gateway.json")
    parser.add_argument("--policy", type=pathlib.Path, default=repo_root / "config/messaging/outbound-mail-policy.json")
    parser.add_argument("--identities", type=pathlib.Path, default=repo_root / "config/messaging/mail-identities.json")
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--require-safe-disabled", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = analyze(load_json(args.gateway), load_json(args.policy), load_json(args.identities))
    except ReadinessError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    text = json.dumps(
        report,
        indent=2 if args.pretty else None,
        sort_keys=True,
        separators=None if args.pretty else (",", ":"),
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    if args.require_safe_disabled and report["readiness_state"] != "safe_disabled":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
