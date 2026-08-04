#!/usr/bin/env python3
"""Validate Phase E readiness reconciliation with accepted WW.CX evidence."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/messaging/outbound_mail_phase_e_evidence.py"
SPEC = importlib.util.spec_from_file_location("phase_e_evidence", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load Phase E evidence module")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


gateway = load("config/messaging/outbound-mail-gateway.json")
policy = load("config/messaging/outbound-mail-policy.json")
identities = load("config/messaging/mail-identities.json")
provider = load("records/messaging/provider-inventories/namecheap-private-email-wwcx-20260802.json")
dns = load("records/messaging/dns-inventories/mail-domain-dns-acceptance-20260804.json")
dkim = load("records/messaging/dns-inventories/wwcx-dkim-dns-acceptance-20260804.json")

os.environ["WWCX_MAIL_SMTP_PASSWORD"] = "SYNTHETIC_SECRET_MUST_NOT_APPEAR"
report = MODULE.reconcile(gateway, policy, identities, provider, dns, dkim)
serialized = json.dumps(report, sort_keys=True)

check(report["contract"] == MODULE.CONTRACT, "evidence report contract mismatch")
check(report["readiness_state"] == "safe_disabled", "committed state must remain safely disabled")
check(report["ready_for_provider_activation"] is False, "evidence report became provider-ready")
check(report["runtime_credentials_inspected"] is False, "base report inspected credentials")
check(report["network_or_dns_queries_performed"] is False, "base report performed network queries")
check(report["message_sent"] is False, "base report recorded message activity")
check("SYNTHETIC_SECRET_MUST_NOT_APPEAR" not in serialized, "environment secret leaked")

codes = {item["code"] for item in report["blockers"]}
check("dkim_evidence_required" not in codes, "generic DKIM blocker was not reconciled")
check("dkim_signing_alignment_unverified" in codes, "signing/alignment blocker is absent")
check("provider_inventory_incomplete" in codes, "provider inventory blocker disappeared")
check("wwcx_dmarc" not in codes, "unexpected synthetic blocker code")

reconciled = report["evidence_reconciliation"]
check(reconciled["wwcx_provider_inventory_accepted"] is True, "provider inventory was not accepted")
check(reconciled["wwcx_active_mailboxes"] == ["blank@ww.cx", "domaincontact@ww.cx"], "accepted mailbox set mismatch")
check(reconciled["canonical_private_mailbox_observed"] is False, "private canonical mailbox was inferred")
check(reconciled["canonical_shared_mailbox_observed"] is False, "shared canonical mailbox was inferred")
check(reconciled["canonical_sender_observed"] is False, "canonical sender was inferred")
check(reconciled["wwcx_catch_all_destination"] == "blank@ww.cx", "Catch-All destination mismatch")
check(reconciled["wwcx_routing_mode"] == "unknown", "routing mode was inferred")
check(reconciled["wwcx_spf_published"] is True, "WW.CX SPF evidence missing")
check(reconciled["wwcx_dmarc_published"] is False, "WW.CX DMARC was incorrectly reported")
check(reconciled["wwcx_dkim_dns_record_observed"] is True, "WW.CX DKIM DNS record evidence missing")
check(reconciled["wwcx_dkim_selector_candidate"] == "default", "WW.CX DKIM selector mismatch")
check(reconciled["wwcx_dkim_provider_signing_verified"] is False, "provider signing was inferred")
check(reconciled["wwcx_dkim_header_alignment_verified"] is False, "header alignment was inferred")
check(reconciled["provider_credentials_inspected"] is False, "evidence reconciliation inspected credentials")
check(reconciled["network_queries_performed"] is False, "evidence reconciliation performed network queries")
check(reconciled["message_sent"] is False, "evidence reconciliation recorded a message")

pilot = report["first_pilot_provider_candidate"]
check(pilot["gateway_profile"] == "smtp_submission", "pilot provider profile mismatch")
check(pilot["provider_family"] == "namecheap_private_email", "pilot provider family mismatch")
check(pilot["provider_selected"] is False, "provider became selected")
check(pilot["credentials_installed"] is False, "credentials became installed")
check(pilot["canonical_sender_available"] is False, "canonical sender became available")
check(pilot["ready"] is False, "pilot provider became ready")

john = next(item for item in report["candidate_senders"] if item["address"] == "john@ww.cx")
check(john["dkim_dns_record_observed"] is True, "john@ww.cx did not inherit public DKIM evidence")
check(john["dkim_selector_candidate"] == "default", "john@ww.cx selector candidate mismatch")
check(john["provider_object_observed"] is False, "john@ww.cx provider object was inferred")
check(john["domain_authentication_verified"] is False, "john@ww.cx authentication was inferred")
check(john["ready_for_pilot"] is False, "john@ww.cx became pilot-ready")

unsafe_dkim = copy.deepcopy(dkim)
unsafe_dkim["assessment"]["provider_signing_verified"] = True
failed_closed = False
try:
    MODULE.reconcile(gateway, policy, identities, provider, dns, unsafe_dkim)
except MODULE.EvidenceReadinessError:
    failed_closed = True
check(failed_closed, "unsafe provider-signing assertion did not fail closed")

unsafe_provider = copy.deepcopy(provider)
unsafe_provider["objects"][0]["access_class"] = "private_john"
failed_closed = False
try:
    MODULE.reconcile(gateway, policy, identities, unsafe_provider, dns, dkim)
except MODULE.EvidenceReadinessError:
    failed_closed = True
check(failed_closed, "inferred provider mailbox access did not fail closed")

with tempfile.TemporaryDirectory() as temporary:
    output = pathlib.Path(temporary) / "phase-e-evidence.json"
    process = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--pretty",
            "--require-safe-disabled",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    check(process.returncode == 0, f"Phase E evidence CLI failed: {process.stderr}")
    cli_report = json.loads(output.read_text(encoding="utf-8"))
    check(cli_report["readiness_state"] == "safe_disabled", "CLI safe-disabled state mismatch")
    check(cli_report["ready_for_provider_activation"] is False, "CLI became provider-ready")

print("Outbound mail Phase E evidence reconciliation validation passed")
print("WW.CX provider, SPF, and public DKIM evidence are accepted without inferring sender readiness")
print("Canonical mailbox, signing/alignment, DMARC, credentials, return-path, and pilot blockers remain")
print("No credential, network query, configuration mutation, activation, or message occurs")
