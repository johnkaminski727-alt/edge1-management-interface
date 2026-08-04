#!/usr/bin/env python3
"""Reconcile accepted provider and DNS evidence into Phase E readiness.

This wrapper preserves the base safe-disabled readiness analysis and refines its
provider/DKIM blockers using committed, read-only acceptance records. It does
not read credential values, query networks, modify configuration, activate a
sender, prepare a message, or send mail.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "messaging"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import outbound_mail_phase_e_readiness as base


CONTRACT = "wwcx.outbound-mail-phase-e-evidence-readiness.v1"
DKIM_CONTRACT = "wwcx.mail-dkim-dns-acceptance.v1"
DNS_CONTRACT = "wwcx.mail-domain-dns-acceptance.v1"
PROVIDER_CONTRACT = "wwcx.provider-mail-objects.v1"


class EvidenceReadinessError(RuntimeError):
    """Raised when an accepted evidence record is malformed or unsafe."""


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceReadinessError(f"unable to read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceReadinessError(f"{path} must contain a JSON object")
    return value


def _require_false(value: Any, label: str) -> None:
    if value is not False:
        raise EvidenceReadinessError(f"{label} must remain false")


def validate_dkim(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("contract") != DKIM_CONTRACT or value.get("read_only") is not True:
        raise EvidenceReadinessError("unsupported or mutable DKIM acceptance")
    if value.get("domain") != "ww.cx" or value.get("provider_family") != "namecheap_private_email":
        raise EvidenceReadinessError("DKIM acceptance domain/provider mismatch")
    default = value.get("selectors", {}).get("default")
    current = value.get("selectors", {}).get("privateemail")
    if not isinstance(default, dict) or not isinstance(current, dict):
        raise EvidenceReadinessError("DKIM selector evidence is incomplete")
    if default.get("state") != "published_valid_shape" or default.get("record_shape_valid") is not True:
        raise EvidenceReadinessError("accepted default DKIM selector is not published with a valid shape")
    if default.get("resolver_consensus") is not True or default.get("authoritative_for_activation") is not False:
        raise EvidenceReadinessError("accepted default DKIM evidence violates the discovery boundary")
    if current.get("state") != "not_observed" or current.get("authoritative_for_activation") is not False:
        raise EvidenceReadinessError("privateemail selector evidence changed")
    assessment = value.get("assessment")
    if not isinstance(assessment, dict):
        raise EvidenceReadinessError("DKIM assessment is absent")
    _require_false(assessment.get("provider_signing_verified"), "provider signing verification")
    _require_false(assessment.get("header_alignment_verified"), "header alignment verification")
    _require_false(assessment.get("ready_for_sender_activation"), "sender readiness")
    _require_false(assessment.get("message_sent"), "message activity")
    boundary = value.get("activation_boundary")
    if not isinstance(boundary, dict) or not boundary:
        raise EvidenceReadinessError("DKIM activation boundary is absent")
    for key, item in boundary.items():
        _require_false(item, f"DKIM activation boundary {key}")
    return {
        "domain": "ww.cx",
        "selector": "default",
        "query_name": default["query_name"],
        "record_sha256": default["record_sha256"],
        "record_shape_valid": True,
        "resolver_consensus": True,
        "provider_signing_verified": False,
        "header_alignment_verified": False,
        "ready_for_sender_activation": False,
    }


def validate_dns(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("contract") != DNS_CONTRACT or value.get("read_only") is not True:
        raise EvidenceReadinessError("unsupported or mutable DNS acceptance")
    domains = value.get("domains")
    if not isinstance(domains, dict) or "ww.cx" not in domains:
        raise EvidenceReadinessError("DNS acceptance does not contain WW.CX")
    wwcx = domains["ww.cx"]
    if wwcx.get("resolver_consensus") is not True:
        raise EvidenceReadinessError("WW.CX DNS resolver consensus is absent")
    if wwcx.get("provider_family") != "namecheap_private_email":
        raise EvidenceReadinessError("WW.CX DNS provider family changed")
    if wwcx.get("dmarc") != []:
        raise EvidenceReadinessError("WW.CX DMARC evidence changed")
    assessment = value.get("assessment")
    if not isinstance(assessment, dict):
        raise EvidenceReadinessError("DNS assessment is absent")
    _require_false(assessment.get("dns_changes_authorized"), "DNS change authorization")
    _require_false(assessment.get("provider_or_sender_activated"), "DNS provider/sender activation")
    _require_false(assessment.get("message_sent"), "DNS evidence message activity")
    return {
        "provider_family": wwcx["provider_family"],
        "mx": list(wwcx.get("mx", [])),
        "spf": list(wwcx.get("spf", [])),
        "dmarc": list(wwcx.get("dmarc", [])),
        "resolver_consensus": True,
    }


def validate_provider(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("contract") != PROVIDER_CONTRACT:
        raise EvidenceReadinessError("unsupported provider inventory contract")
    source = value.get("source")
    if not isinstance(source, dict) or source.get("read_only") is not True:
        raise EvidenceReadinessError("provider inventory must be read-only")
    if value.get("provider_family") != "namecheap_private_email":
        raise EvidenceReadinessError("provider inventory family changed")
    objects = value.get("objects")
    if not isinstance(objects, list):
        raise EvidenceReadinessError("provider inventory objects are absent")
    addresses = sorted(
        item.get("address")
        for item in objects
        if isinstance(item, dict) and item.get("active") is True
    )
    if addresses != ["blank@ww.cx", "domaincontact@ww.cx"]:
        raise EvidenceReadinessError("accepted WW.CX mailbox set changed")
    for item in objects:
        if item.get("access_class") != "unknown":
            raise EvidenceReadinessError("provider mailbox access was inferred")
    defaults = value.get("default_addresses")
    if defaults != [{"domain": "ww.cx", "behavior": "forward", "destination": "blank@ww.cx"}]:
        raise EvidenceReadinessError("WW.CX Catch-All evidence changed")
    routing = value.get("domain_routing")
    if routing != [{"domain": "ww.cx", "mode": "unknown"}]:
        raise EvidenceReadinessError("WW.CX routing evidence changed")
    return {
        "active_mailboxes": addresses,
        "canonical_private_mailbox_observed": "john-inbox@ww.cx" in addresses,
        "canonical_shared_mailbox_observed": "maildesk@ww.cx" in addresses,
        "canonical_sender_observed": "john@ww.cx" in addresses,
        "catch_all_destination": "blank@ww.cx",
        "routing_mode": "unknown",
        "forwarding_and_filters_verified": False,
        "access_ownership_verified": False,
    }


def _replace_blocker(report: dict[str, Any], old_code: str, replacement: dict[str, str]) -> None:
    blockers = [item for item in report["blockers"] if item.get("code") != old_code]
    blockers.append(replacement)
    report["blockers"] = blockers
    report["blocker_count"] = len(blockers)


def reconcile(
    gateway: dict[str, Any],
    policy: dict[str, Any],
    identities: dict[str, Any],
    provider_acceptance: dict[str, Any],
    dns_acceptance: dict[str, Any],
    dkim_acceptance: dict[str, Any],
) -> dict[str, Any]:
    report = base.analyze(gateway, policy, identities)
    provider = validate_provider(provider_acceptance)
    dns = validate_dns(dns_acceptance)
    dkim = validate_dkim(dkim_acceptance)

    _replace_blocker(
        report,
        "dkim_evidence_required",
        {
            "code": "dkim_signing_alignment_unverified",
            "category": "domain_authentication",
            "detail": "A valid-shape public DKIM record is accepted at default._domainkey.ww.cx, but no controlled received message proves provider signing, selector use, signing-domain alignment, or receiver verification.",
            "required_action": "After every other pilot gate is ready, send one exact authorized message to a WW.CX-controlled inbox and preserve complete authentication headers.",
            "approval_boundary": "production_message_traffic",
        },
    )
    _replace_blocker(
        report,
        "provider_inventory_incomplete",
        {
            "code": "provider_inventory_incomplete",
            "category": "evidence",
            "detail": "The WW.CX provider-visible inventory is accepted, but canonical internal destinations and john@ww.cx are not observed; forwarding, filters, access ownership and routing remain unresolved.",
            "required_action": "Complete read-only mailbox settings and routing evidence, then decide the canonical mailbox and sender objects without mutating provider state.",
            "approval_boundary": "provider_access",
        },
    )

    for sender in report["candidate_senders"]:
        address = sender.get("address", "")
        if isinstance(address, str) and address.endswith("@ww.cx"):
            sender["dkim_dns_record_observed"] = True
            sender["dkim_selector_candidate"] = "default"
            sender["provider_object_observed"] = address in provider["active_mailboxes"]
            sender["domain_authentication_verified"] = False
            sender["ready_for_pilot"] = False
        else:
            sender["dkim_dns_record_observed"] = False
            sender["provider_object_observed"] = False

    report.update(
        {
            "contract": CONTRACT,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "evidence_reconciliation": {
                "wwcx_provider_inventory_accepted": True,
                "wwcx_provider_family": provider_acceptance["provider_family"],
                "wwcx_active_mailboxes": provider["active_mailboxes"],
                "canonical_private_mailbox_observed": provider["canonical_private_mailbox_observed"],
                "canonical_shared_mailbox_observed": provider["canonical_shared_mailbox_observed"],
                "canonical_sender_observed": provider["canonical_sender_observed"],
                "wwcx_catch_all_destination": provider["catch_all_destination"],
                "wwcx_routing_mode": provider["routing_mode"],
                "wwcx_spf_published": bool(dns["spf"]),
                "wwcx_dmarc_published": bool(dns["dmarc"]),
                "wwcx_dkim_dns_record_observed": True,
                "wwcx_dkim_selector_candidate": dkim["selector"],
                "wwcx_dkim_record_sha256": dkim["record_sha256"],
                "wwcx_dkim_provider_signing_verified": False,
                "wwcx_dkim_header_alignment_verified": False,
                "provider_credentials_inspected": False,
                "network_queries_performed": False,
                "message_sent": False,
            },
            "first_pilot_provider_candidate": {
                "gateway_profile": "smtp_submission",
                "provider_family": "namecheap_private_email",
                "provider_selected": False,
                "provider_terms_reviewed": False,
                "credentials_installed": False,
                "canonical_sender_available": provider["canonical_sender_observed"],
                "ready": False,
            },
        }
    )
    report["ready_for_provider_activation"] = False
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", type=pathlib.Path, default=ROOT / "config/messaging/outbound-mail-gateway.json")
    parser.add_argument("--policy", type=pathlib.Path, default=ROOT / "config/messaging/outbound-mail-policy.json")
    parser.add_argument("--identities", type=pathlib.Path, default=ROOT / "config/messaging/mail-identities.json")
    parser.add_argument("--provider-acceptance", type=pathlib.Path, default=ROOT / "records/messaging/provider-inventories/namecheap-private-email-wwcx-20260802.json")
    parser.add_argument("--dns-acceptance", type=pathlib.Path, default=ROOT / "records/messaging/dns-inventories/mail-domain-dns-acceptance-20260804.json")
    parser.add_argument("--dkim-acceptance", type=pathlib.Path, default=ROOT / "records/messaging/dns-inventories/wwcx-dkim-dns-acceptance-20260804.json")
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--require-safe-disabled", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = reconcile(
            base.load_json(args.gateway),
            base.load_json(args.policy),
            base.load_json(args.identities),
            load_json(args.provider_acceptance),
            load_json(args.dns_acceptance),
            load_json(args.dkim_acceptance),
        )
    except (base.ReadinessError, EvidenceReadinessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    rendered = json.dumps(
        report,
        indent=2 if args.pretty else None,
        sort_keys=True,
        separators=None if args.pretty else (",", ":"),
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    if args.require_safe_disabled and report["readiness_state"] != "safe_disabled":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
