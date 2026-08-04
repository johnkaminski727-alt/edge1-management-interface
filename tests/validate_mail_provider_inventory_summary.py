#!/usr/bin/env python3
"""Validate the reconciled multi-domain mail provider inventory summary."""

from __future__ import annotations

import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "docs/messaging/mail-provider-inventory.md"
INVENTORY = ROOT / "records/messaging/provider-inventories/namecheap-private-email-wwcx-20260802.json"
ACCEPTANCE = ROOT / "docs/messaging-operations/namecheap-private-email-inventory-acceptance-20260802.md"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


text = SUMMARY.read_text(encoding="utf-8")
check(INVENTORY.is_file(), "normalized WW.CX provider inventory is absent")
check(ACCEPTANCE.is_file(), "WW.CX provider acceptance record is absent")
check("namecheap-private-email-wwcx-20260802.json" in text, "summary does not reference normalized WW.CX inventory")
check("blank@ww.cx" in text and "domaincontact@ww.cx" in text, "summary omits observed WW.CX mailboxes")
check("Catch-All" in text and "blank@ww.cx" in text, "summary omits Catch-All state")
check("john-inbox@ww.cx" in text and "Not observed" in text, "summary does not preserve canonical mailbox gap")
check("maildesk@ww.cx" in text, "summary omits shared canonical mailbox")
check("not ready for pilot" in text.casefold(), "summary does not preserve no-pilot conclusion")
check("routing" in text.casefold() and "unknown" in text.casefold(), "summary omits unknown routing state")
check("forwarding" in text.casefold() and "filter" in text.casefold(), "summary omits mailbox-level evidence gaps")
check("provider-admin inventory still required" not in text, "summary retains stale no-provider-inventory assessment")
check("provider-admin exports have not been obtained" not in text, "summary retains stale export blocker")
check("DKIM selectors and signing status remain unknown for all five domains" not in text, "summary ignores accepted WW.CX default-selector evidence")
check("accepted 2026-08-01 snapshot" in text, "summary does not bound DNS evidence by capture date")
check(not re.search(r"support\s+pin\s*[:=]?\s*\d+", text, re.I), "summary contains support PIN material")
check(not re.search(r"password\s*[:=]\s*\S+", text, re.I), "summary contains password-like material")

print("Mail provider inventory summary validation passed")
print("Accepted WW.CX evidence, stale-state removal, unresolved gaps, and no-secret boundaries verified")
