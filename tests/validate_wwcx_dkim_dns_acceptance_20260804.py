#!/usr/bin/env python3
"""Validate the accepted public WW.CX DKIM candidate evidence."""

from __future__ import annotations

import json
import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / "records/messaging/dns-inventories/wwcx-dkim-dns-acceptance-20260804.json"
CANDIDATES = ROOT / "config/messaging/mail-dkim-selector-candidates.json"
OUTBOUND = ROOT / "config/messaging/outbound-mail-gateway.json"
POLICY = ROOT / "config/messaging/outbound-mail-policy.json"
IDENTITIES = ROOT / "config/messaging/mail-identities.json"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


acceptance = load(ACCEPTANCE)
candidates = load(CANDIDATES)
outbound = load(OUTBOUND)
policy = load(POLICY)
identities = load(IDENTITIES)
serialized = json.dumps(acceptance, sort_keys=True)

check(acceptance["contract"] == "wwcx.mail-dkim-dns-acceptance.v1", "acceptance contract mismatch")
check(acceptance["domain"] == "ww.cx", "acceptance domain mismatch")
check(acceptance["provider_family"] == "namecheap_private_email", "provider family mismatch")
check(acceptance["read_only"] is True, "acceptance must remain read-only")
check(acceptance["observed_at"] == "2026-08-04T00:44:53+00:00", "observation timestamp mismatch")
check(acceptance["source"]["workflow_run_id"] == 30866538424, "workflow run mismatch")
check(acceptance["source"]["artifact_id"] == 8876301894, "artifact ID mismatch")
check(acceptance["source"]["head_sha"] == "8458f02398d450f92a720e0fe4aab1f91f06563e", "source commit mismatch")
for key in ("artifact_sha256", "manifest_record_sha256"):
    check(bool(re.fullmatch(r"[0-9a-f]{64}", acceptance["source"][key])), f"invalid {key}")
check(set(acceptance["source"]["resolvers"]) == {"cloudflare", "google"}, "resolver set mismatch")

configured = {
    item["selector"]
    for item in candidates["domains"]["ww.cx"]["candidates"]
}
check(set(acceptance["selectors"]) == configured == {"default", "privateemail"}, "selector set mismatch")

default = acceptance["selectors"]["default"]
check(default["query_name"] == "default._domainkey.ww.cx", "default query name mismatch")
check(default["state"] == "published_valid_shape", "default selector was not accepted as published")
check(default["record_shape_valid"] is True, "default record shape invalid")
check(default["resolver_consensus"] is True, "default resolver consensus failed")
check(default["successful_resolvers"] == default["resolver_count"] == 2, "default resolver count mismatch")
check(default["key_type"] == "rsa", "default key type mismatch")
check(default["public_key_character_count"] == 392, "default public-key length mismatch")
check(default["record_character_count"] == 408, "default record length mismatch")
check(bool(re.fullmatch(r"[0-9a-f]{64}", default["record_sha256"])), "default record digest invalid")
check(default["authoritative_for_activation"] is False, "default selector became activation-authoritative")

current = acceptance["selectors"]["privateemail"]
check(current["query_name"] == "privateemail._domainkey.ww.cx", "privateemail query name mismatch")
check(current["state"] == "not_observed", "privateemail selector observation changed")
check(current["dkim_answer_count"] == 0, "privateemail selector unexpectedly has an answer")
check(current["resolver_consensus"] is True, "privateemail resolver consensus failed")
check(current["authoritative_for_activation"] is False, "privateemail selector became activation-authoritative")

assessment = acceptance["assessment"]
check(assessment["candidate_selector_observed"] == "default", "observed selector assessment mismatch")
check(assessment["provider_report_consistent"] is True, "provider-report consistency changed")
check(assessment["dns_record_shape_valid"] is True, "DNS shape assessment changed")
check(assessment["privateemail_candidate_observed"] is False, "privateemail assessment changed")
check(assessment["provider_signing_verified"] is False, "provider signing was incorrectly verified")
check(assessment["header_alignment_verified"] is False, "header alignment was incorrectly verified")
check(assessment["ready_for_sender_activation"] is False, "DKIM DNS evidence became sender-ready")
check(assessment["message_sent"] is False, "message activity appeared")
check(all(value is False for value in acceptance["activation_boundary"].values()), "activation boundary changed")

check("p=" not in serialized.casefold(), "public key material was stored in the acceptance record")
check("miib" not in serialized.casefold(), "public key prefix was stored in the acceptance record")
check("password" not in serialized.casefold(), "password-like material was stored")
check("support pin" not in serialized.casefold(), "support verification material was stored")

check(outbound["enabled"] is False, "gateway became enabled")
check(outbound["external_delivery_authorized"] is False, "external delivery became authorized")
check(outbound["admin"]["send_endpoint_enabled"] is False, "send endpoint became enabled")
check(policy["enabled"] is False, "outbound policy became enabled")
check(policy["smtp_cutover_authorized"] is False, "SMTP cutover became authorized")
check(identities["outbound_activation_authorized"] is False, "sender activation became authorized")
check(identities["sender_selection"]["live_sender_allowlist"] == [], "live sender allowlist is not empty")

print("WW.CX DKIM DNS acceptance validation passed")
print("The public default selector is present with resolver consensus")
print("Provider signing and received-header alignment remain unverified")
print("No key material, credential, DNS mutation, activation, or message is recorded")
