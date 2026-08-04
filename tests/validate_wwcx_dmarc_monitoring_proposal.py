#!/usr/bin/env python3
"""Validate the conservative, non-deploying WW.CX DMARC proposal."""

from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/messaging/wwcx_dmarc_monitoring_proposal.py"
DOC = ROOT / "docs/messaging-operations/wwcx-dmarc-monitoring-proposal-20260804.md"
SPEC = importlib.util.spec_from_file_location("dmarc_proposal", TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load DMARC proposal module")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


for path in (TOOL, DOC):
    check(path.is_file(), f"missing {path}")
    check(path.stat().st_size > 500, f"undersized {path}")

provider = load("records/messaging/provider-inventories/namecheap-private-email-wwcx-20260802.json")
dns = load("records/messaging/dns-inventories/mail-domain-dns-acceptance-20260804.json")
dkim = load("records/messaging/dns-inventories/wwcx-dkim-dns-acceptance-20260804.json")
proposal = MODULE.build_proposal(provider, dns, dkim, "domaincontact@ww.cx")
serialized = json.dumps(proposal, sort_keys=True)

check(proposal["contract"] == MODULE.CONTRACT, "proposal contract mismatch")
check(proposal["domain"] == "ww.cx", "proposal domain mismatch")
check(proposal["record_name"] == "_dmarc.ww.cx", "proposal record name mismatch")
check(proposal["record_type"] == "TXT", "proposal record type mismatch")
check(
    proposal["proposed_value"]
    == "v=DMARC1; p=none; sp=none; adkim=r; aspf=r; pct=100; rua=mailto:domaincontact@ww.cx; ri=86400",
    "proposed DMARC value changed",
)
check(proposal["policy"] == "none", "DMARC policy is not monitoring-only")
check(proposal["subdomain_policy"] == "none", "DMARC subdomain policy is not monitoring-only")
check(proposal["dkim_alignment_mode"] == "relaxed", "DKIM alignment mode changed")
check(proposal["spf_alignment_mode"] == "relaxed", "SPF alignment mode changed")
check(proposal["forensic_reporting_requested"] is False, "forensic reporting was enabled")
check("ruf=" not in proposal["proposed_value"].casefold(), "forensic reporting URI entered record")
check("p=quarantine" not in serialized and "p=reject" not in serialized, "enforcement policy entered proposal")

accepted = proposal["evidence"]
check(accepted["active_provider_mailboxes"] == ["blank@ww.cx", "domaincontact@ww.cx"], "provider mailbox evidence changed")
check(accepted["report_mailbox_provider_object_observed"] is True, "report mailbox object was not observed")
check(accepted["report_mailbox_access_verified"] is False, "report mailbox access was inferred")
check(accepted["report_mailbox_receipt_verified"] is False, "report mailbox receipt was inferred")
check(accepted["aggregate_report_processing_ready"] is False, "report processing became ready")
check(accepted["existing_dmarc_records"] == [], "existing DMARC evidence changed")
check(accepted["accepted_spf_records"] == ["v=spf1 include:spf.privateemail.com ~all"], "accepted SPF evidence changed")
check(accepted["accepted_dkim_selector"] == "default", "accepted DKIM selector changed")
check(accepted["provider_signing_verified"] is False, "provider signing was inferred")
check(accepted["header_alignment_verified"] is False, "header alignment was inferred")

check(all(value is False for value in proposal["authorization"].values()), "proposal created authorization")
readiness = proposal["readiness"]
check(readiness["record_syntax_ready"] is True, "record syntax was not ready")
check(readiness["report_destination_object_observed"] is True, "report destination object missing")
check(readiness["report_destination_access_ready"] is False, "report mailbox access became ready")
check(readiness["report_processing_ready"] is False, "report processing became ready")
check(readiness["dns_change_ready"] is False, "DNS proposal became change-ready")
check(readiness["pilot_authentication_ready"] is False, "proposal became pilot-ready")
for key in (
    "network_queries_performed",
    "dns_modified",
    "mailbox_accessed",
    "credentials_inspected",
    "message_sent",
):
    check(proposal[key] is False, f"proposal changed safety marker {key}")

blank_proposal = MODULE.build_proposal(provider, dns, dkim, "blank@ww.cx")
check(blank_proposal["aggregate_report_address"] == "blank@ww.cx", "observed alternate mailbox was rejected")
check(blank_proposal["readiness"]["dns_change_ready"] is False, "alternate mailbox made DNS ready")

invalid_cases: list[tuple[str, dict, dict, dict, str]] = []
invalid_cases.append(("unobserved report mailbox", provider, dns, dkim, "dmarc@ww.cx"))
existing_dmarc = copy.deepcopy(dns)
existing_dmarc["domains"]["ww.cx"]["dmarc"] = ["v=DMARC1; p=none"]
invalid_cases.append(("existing DMARC record", provider, existing_dmarc, dkim, "domaincontact@ww.cx"))
unsafe_dkim = copy.deepcopy(dkim)
unsafe_dkim["assessment"]["provider_signing_verified"] = True
invalid_cases.append(("inferred provider signing", provider, dns, unsafe_dkim, "domaincontact@ww.cx"))
unsafe_provider = copy.deepcopy(provider)
unsafe_provider["source"]["read_only"] = False
invalid_cases.append(("mutable provider evidence", unsafe_provider, dns, dkim, "domaincontact@ww.cx"))
external_address = "reports@example.com"
invalid_cases.append(("external report address", provider, dns, dkim, external_address))

for label, provider_value, dns_value, dkim_value, address in invalid_cases:
    failed_closed = False
    try:
        MODULE.build_proposal(provider_value, dns_value, dkim_value, address)
    except MODULE.DmarcProposalError:
        failed_closed = True
    check(failed_closed, f"invalid {label} did not fail closed")

with tempfile.TemporaryDirectory() as temporary:
    output = pathlib.Path(temporary) / "proposal.json"
    process = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--pretty",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    check(process.returncode == 0, f"DMARC proposal CLI failed: {process.stderr}")
    cli_proposal = json.loads(output.read_text(encoding="utf-8"))
    check(cli_proposal["proposed_value"] == proposal["proposed_value"], "CLI proposal differs")
    check(cli_proposal["readiness"]["dns_change_ready"] is False, "CLI proposal became DNS-ready")

source = TOOL.read_text(encoding="utf-8")
for required in (
    "non-deploying WW.CX DMARC monitoring proposal",
    "report_mailbox_access_verified",
    "aggregate_report_processing_ready",
    "dns_change_authorized",
    "ready",
    "network_queries_performed",
    "dns_modified",
    "mailbox_accessed",
    "message_sent",
):
    check(required in source, f"proposal tool missing safety marker: {required}")
for prohibited in (
    "requests.",
    "urllib.request",
    "dnspython",
    "subprocess.",
    "nsupdate",
    "cloudflare",
    "create_record",
    "update_record",
    "delete_record",
    "smtplib",
    "imaplib",
):
    check(prohibited not in source, f"proposal tool contains prohibited operation: {prohibited}")

print("WW.CX DMARC monitoring proposal validation passed")
print("Exact p=none record uses an active provider-observed WW.CX aggregate-report mailbox")
print("Mailbox access, report processing, DNS authorization, and pilot readiness remain false")
print("No forensic reporting, enforcement, network query, DNS mutation, credential, or message occurs")
