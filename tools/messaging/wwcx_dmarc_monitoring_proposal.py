#!/usr/bin/env python3
"""Generate a conservative, non-deploying WW.CX DMARC monitoring proposal.

The tool reconciles committed provider and DNS evidence, selects only an
observed WW.CX mailbox as the aggregate-report destination, and emits an exact
p=none TXT proposal. It never queries or changes DNS, accesses the mailbox,
inspects credentials, authorizes a change, or sends mail.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import datetime, timezone
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
PROVIDER_DEFAULT = (
    ROOT
    / "records/messaging/provider-inventories/namecheap-private-email-wwcx-20260802.json"
)
DNS_DEFAULT = (
    ROOT
    / "records/messaging/dns-inventories/mail-domain-dns-acceptance-20260804.json"
)
DKIM_DEFAULT = (
    ROOT
    / "records/messaging/dns-inventories/wwcx-dkim-dns-acceptance-20260804.json"
)
CONTRACT = "wwcx.dmarc-monitoring-proposal.v1"
ADDRESS_RE = re.compile(r"^[^@\s]+@([^@\s]+)$")


class DmarcProposalError(RuntimeError):
    """Raised when accepted evidence cannot support a conservative proposal."""


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DmarcProposalError(f"unable to read accepted evidence: {exc}") from exc
    if not isinstance(value, dict):
        raise DmarcProposalError(f"accepted evidence must be an object: {path}")
    return value


def active_mailboxes(provider: dict[str, Any]) -> list[str]:
    if provider.get("contract") != "wwcx.provider-mail-objects.v1":
        raise DmarcProposalError("unsupported provider inventory contract")
    if provider.get("provider_family") != "namecheap_private_email":
        raise DmarcProposalError("WW.CX provider inventory family mismatch")
    source = provider.get("source")
    if not isinstance(source, dict) or source.get("read_only") is not True:
        raise DmarcProposalError("provider inventory is not accepted read-only evidence")
    objects = provider.get("objects")
    if not isinstance(objects, list):
        raise DmarcProposalError("provider inventory objects are absent")
    result = sorted(
        str(item.get("address", "")).casefold()
        for item in objects
        if isinstance(item, dict)
        and item.get("object_type") == "mailbox"
        and item.get("active") is True
    )
    if not result:
        raise DmarcProposalError("provider inventory has no active WW.CX mailbox")
    return result


def accepted_dns(dns: dict[str, Any]) -> dict[str, Any]:
    if dns.get("contract") != "wwcx.mail-domain-dns-acceptance.v1":
        raise DmarcProposalError("unsupported DNS acceptance contract")
    if dns.get("read_only") is not True:
        raise DmarcProposalError("DNS acceptance is not read-only")
    wwcx = dns.get("domains", {}).get("ww.cx")
    if not isinstance(wwcx, dict):
        raise DmarcProposalError("DNS acceptance does not contain WW.CX")
    if wwcx.get("resolver_consensus") is not True:
        raise DmarcProposalError("WW.CX DNS resolver consensus is absent")
    if wwcx.get("provider_family") != "namecheap_private_email":
        raise DmarcProposalError("WW.CX DNS provider family changed")
    if wwcx.get("dmarc") != []:
        raise DmarcProposalError("WW.CX already has a published DMARC record")
    spf = wwcx.get("spf")
    if not isinstance(spf, list) or len(spf) != 1:
        raise DmarcProposalError("accepted WW.CX SPF evidence is absent or ambiguous")
    return wwcx


def accepted_dkim(dkim: dict[str, Any]) -> dict[str, Any]:
    if dkim.get("contract") != "wwcx.mail-dkim-dns-acceptance.v1":
        raise DmarcProposalError("unsupported DKIM acceptance contract")
    if dkim.get("read_only") is not True or dkim.get("domain") != "ww.cx":
        raise DmarcProposalError("DKIM acceptance scope mismatch")
    default = dkim.get("selectors", {}).get("default")
    if not isinstance(default, dict):
        raise DmarcProposalError("default DKIM selector evidence is absent")
    if default.get("state") != "published_valid_shape":
        raise DmarcProposalError("default DKIM selector is not publicly accepted")
    if default.get("resolver_consensus") is not True:
        raise DmarcProposalError("default DKIM resolver consensus is absent")
    assessment = dkim.get("assessment")
    if not isinstance(assessment, dict):
        raise DmarcProposalError("DKIM assessment is absent")
    if assessment.get("provider_signing_verified") is not False:
        raise DmarcProposalError("DKIM evidence incorrectly claims provider signing")
    if assessment.get("header_alignment_verified") is not False:
        raise DmarcProposalError("DKIM evidence incorrectly claims header alignment")
    return default


def build_proposal(
    provider: dict[str, Any],
    dns: dict[str, Any],
    dkim: dict[str, Any],
    report_address: str,
) -> dict[str, Any]:
    mailboxes = active_mailboxes(provider)
    wwcx_dns = accepted_dns(dns)
    default_dkim = accepted_dkim(dkim)
    address = report_address.strip().casefold()
    match = ADDRESS_RE.fullmatch(address)
    if not match or match.group(1).casefold() != "ww.cx":
        raise DmarcProposalError("aggregate-report address must be a WW.CX mailbox")
    if address not in mailboxes:
        raise DmarcProposalError(
            "aggregate-report address is not an active provider-observed mailbox"
        )

    record = (
        "v=DMARC1; p=none; sp=none; adkim=r; aspf=r; pct=100; "
        f"rua=mailto:{address}; ri=86400"
    )
    return {
        "contract": CONTRACT,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "domain": "ww.cx",
        "record_name": "_dmarc.ww.cx",
        "record_type": "TXT",
        "proposed_value": record,
        "policy": "none",
        "subdomain_policy": "none",
        "dkim_alignment_mode": "relaxed",
        "spf_alignment_mode": "relaxed",
        "percentage": 100,
        "aggregate_report_interval_seconds": 86400,
        "aggregate_report_address": address,
        "forensic_reporting_requested": False,
        "evidence": {
            "provider_family": provider["provider_family"],
            "active_provider_mailboxes": mailboxes,
            "report_mailbox_provider_object_observed": True,
            "report_mailbox_access_verified": False,
            "report_mailbox_receipt_verified": False,
            "aggregate_report_processing_ready": False,
            "existing_dmarc_records": list(wwcx_dns["dmarc"]),
            "accepted_spf_records": list(wwcx_dns["spf"]),
            "accepted_dkim_selector": "default",
            "accepted_dkim_record_sha256": default_dkim["record_sha256"],
            "provider_signing_verified": False,
            "header_alignment_verified": False,
        },
        "authorization": {
            "dns_change_authorized": False,
            "mailbox_access_authorized": False,
            "report_processing_authorized": False,
            "provider_or_sender_activation_authorized": False,
            "message_authorized": False,
        },
        "readiness": {
            "record_syntax_ready": True,
            "report_destination_object_observed": True,
            "report_destination_access_ready": False,
            "report_processing_ready": False,
            "dns_change_ready": False,
            "pilot_authentication_ready": False,
        },
        "network_queries_performed": False,
        "dns_modified": False,
        "mailbox_accessed": False,
        "credentials_inspected": False,
        "message_sent": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", type=pathlib.Path, default=PROVIDER_DEFAULT)
    parser.add_argument("--dns", type=pathlib.Path, default=DNS_DEFAULT)
    parser.add_argument("--dkim", type=pathlib.Path, default=DKIM_DEFAULT)
    parser.add_argument("--report-address", default="domaincontact@ww.cx")
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build_proposal(
            load_json(args.provider),
            load_json(args.dns),
            load_json(args.dkim),
            args.report_address,
        )
    except DmarcProposalError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    rendered = json.dumps(
        report,
        indent=2 if args.pretty else None,
        sort_keys=True,
        separators=None if args.pretty else (",", ":"),
    ) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
