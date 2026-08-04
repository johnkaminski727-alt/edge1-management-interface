#!/usr/bin/env python3
"""Validate the accepted WW.CX Namecheap Private Email inventory."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "records/messaging/provider-inventories/namecheap-private-email-wwcx-20260802.json"
MODULE_PATH = ROOT / "tools/messaging/reconcile_mail_provider_objects.py"
SPEC = importlib.util.spec_from_file_location("provider_reconcile", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load provider reconciliation module")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def walk(value, path: str = "root"):
    if isinstance(value, dict):
        for key, item in value.items():
            yield path + "." + str(key), key, item
            yield from walk(item, path + "." + str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk(item, f"{path}[{index}]")


inventory = load(INVENTORY_PATH)
normalized = MODULE.validate_inventory(inventory, "namecheap_private_email_wwcx")
check(normalized["provider_id"] == "namecheap-private-email-wwcx", "provider ID mismatch")
check(normalized["provider_family"] == "namecheap_private_email", "provider family mismatch")
check(normalized["source"]["read_only"] is True, "source must remain read-only")
check(len(normalized["objects"]) == 2, "expected exactly two provider-visible mailboxes")

objects = {item["address"]: item for item in normalized["objects"]}
check(set(objects) == {"blank@ww.cx", "domaincontact@ww.cx"}, "mailbox inventory mismatch")
for address, item in objects.items():
    check(item["object_type"] == "mailbox", f"{address} must be a mailbox")
    check(item["active"] is True and item["receives_mail"] is True, f"{address} active receive state mismatch")
    check(item["can_send"] is True, f"{address} provider send capability mismatch")
    check(item["access_class"] == "unknown", f"{address} access must remain unproven")
    check(item["quota_bytes"] == 10737418240, f"{address} quota mismatch")
    notes = item["notes"].casefold()
    check("unverified" in notes, f"{address} notes must preserve unresolved state")
    check("auto-forward" in notes and "filter" in notes, f"{address} notes omit mailbox-level gaps")

check(normalized["default_addresses"] == [{
    "provider_id": "namecheap-private-email-wwcx",
    "domain": "ww.cx",
    "behavior": "forward",
    "destination": "blank@ww.cx",
}], "catch-all normalization mismatch")
check(normalized["domain_routing"] == [{
    "provider_id": "namecheap-private-email-wwcx",
    "domain": "ww.cx",
    "mode": "unknown",
}], "routing mode must remain unknown")

for path, key, value in walk(inventory):
    if isinstance(key, str):
        check(not re.search(r"password|secret|token|support.?pin|cookie|private.?key", key, re.I), f"secret-bearing field at {path}")
    if isinstance(value, str):
        check(not re.search(r"support\s+pin\s*[:=]?\s*\d+", value, re.I), f"support PIN material at {path}")
        check("reset link" not in value.casefold(), f"reset-link material at {path}")

inbound = load(ROOT / "config/messaging/inbound-mail-hub.json")
identities = load(ROOT / "config/messaging/mail-identities.json")
report = MODULE.reconcile(inbound, identities, [inventory])
check(report["read_only"] is True, "reconciliation must remain read-only")
check(report["summary"]["observed_address_count"] == 2, "observed address count mismatch")
check(report["summary"]["ready_for_pilot"] is False, "partial provider inventory became pilot-ready")
check(report["summary"]["critical_gap_count"] > 0, "expected canonical route gaps are absent")

warning_types = {item["type"] for item in report["warnings"]}
check("unexpected_managed_addresses" in warning_types, "unexpected WW.CX mailboxes were not flagged")
check("non_reject_default_addresses" in warning_types, "Catch-All warning is absent")
check("unresolved_domain_routing_modes" in warning_types, "unknown routing warning is absent")

unexpected = next(item["items"] for item in report["warnings"] if item["type"] == "unexpected_managed_addresses")
check(unexpected == ["blank@ww.cx", "domaincontact@ww.cx"], "unexpected mailbox warning mismatch")

internal = {item["address"]: item["status"] for item in report["internal_mailboxes"]}
check(internal.get("john-inbox@ww.cx") == "not_observed", "private canonical mailbox was incorrectly inferred")
check(internal.get("maildesk@ww.cx") == "not_observed", "shared canonical mailbox was incorrectly inferred")

sender = {item["address"]: item["status"] for item in report["sender_status"]}
check(sender.get("john@ww.cx") == "not_sender_capable_or_not_observed", "canonical sender capability was incorrectly inferred")

print("Namecheap Private Email WW.CX inventory validation passed")
print("Two active mailboxes, Catch-All warning, unknown routing, unknown access, and unresolved canonical routes verified")
