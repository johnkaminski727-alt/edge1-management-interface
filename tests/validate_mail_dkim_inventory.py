#!/usr/bin/env python3
"""Validate the read-only WW.CX DKIM candidate inventory tooling."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/messaging/mail_dkim_inventory.py"
CONFIG = ROOT / "config/messaging/mail-dkim-selector-candidates.json"
DOC = ROOT / "docs/messaging-operations/wwcx-dkim-candidate-discovery-20260804.md"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


for path in (TOOL, CONFIG, DOC):
    check(path.is_file(), f"missing {path}")
    check(path.stat().st_size > 500, f"undersized {path}")

config = json.loads(CONFIG.read_text(encoding="utf-8"))
check(config["contract"] == "wwcx.mail-dkim-selector-candidates.v1", "candidate contract mismatch")
check(config["read_only"] is True, "candidate config must remain read-only")
check(set(config["domains"]) == {"ww.cx"}, "candidate domain scope expanded")
selectors = [item["selector"] for item in config["domains"]["ww.cx"]["candidates"]]
check(selectors == ["default", "privateemail"], "WW.CX candidate selectors changed")
check(all(item["authoritative_for_activation"] is False for item in config["domains"]["ww.cx"]["candidates"]), "candidate became activation-authoritative")
check(all(value is False for value in config["activation_boundary"].values()), "activation boundary changed")

text = TOOL.read_text(encoding="utf-8")
for required in (
    "read-only public DNS inventory",
    "A published key is evidence of a DNS record only",
    "provider_signing_verified",
    "header_alignment_verified",
    "ready_for_sender_activation",
    "credentials_inspected",
    "dns_modified",
    "message_sent",
    "record_sha256",
    "public_key_character_count",
    "resolver_disagreement",
):
    check(required in text, f"tool is missing {required}")
for prohibited in (
    "boto3",
    "requests.",
    "subprocess.",
    "dnspython",
    "update_record",
    "delete_record",
    "create_record",
    "send_message",
    "smtplib",
):
    check(prohibited not in text, f"tool contains prohibited operation {prohibited}")

compile_result = subprocess.run(
    [sys.executable, "-m", "py_compile", str(TOOL)],
    cwd=ROOT,
    check=False,
)
check(compile_result.returncode == 0, "DKIM inventory tool did not compile")

unit_result = subprocess.run(
    [sys.executable, "-m", "unittest", "tests.test_mail_dkim_inventory"],
    cwd=ROOT,
    check=False,
)
check(unit_result.returncode == 0, "DKIM inventory unit tests failed")

print("WW.CX DKIM candidate inventory validation passed")
print("Both documented Namecheap Private Email selectors remain discovery-only")
print("Public keys are minimized to hashes and lengths in evidence")
print("DNS record presence cannot enable a sender or prove signing/alignment")
print("No provider login, credential inspection, DNS mutation, or message traffic occurs")
