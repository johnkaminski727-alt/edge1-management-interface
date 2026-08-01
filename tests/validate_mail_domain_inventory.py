#!/usr/bin/env python3
"""Repository validation for the read-only mail-domain inventory tool."""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "messaging" / "mail_domain_inventory.py"
WORKFLOW = ROOT / ".github" / "workflows" / "mail-domain-inventory.yml"

assert TOOL.is_file()
assert TOOL.stat().st_size > 1000
assert WORKFLOW.is_file()
assert WORKFLOW.stat().st_size > 500

source = TOOL.read_text(encoding="utf-8")
for token in (
    "cloudflare-dns.com/dns-query",
    "dns.google/resolve",
    "wwcx.mail-domain-dns-inventory.v1",
    "read_only",
    "infer_mail_provider",
    "_dmarc.",
):
    assert token in source, token

workflow = WORKFLOW.read_text(encoding="utf-8")
for token in (
    "workflow_dispatch",
    "pull_request",
    "mail-domain-inventory.json",
    "actions/upload-artifact@v4",
):
    assert token in workflow, token

result = subprocess.run(
    [sys.executable, "-m", "unittest", "tests.test_mail_domain_inventory"],
    cwd=ROOT,
    check=False,
)
assert result.returncode == 0

compile_result = subprocess.run(
    [sys.executable, "-m", "py_compile", str(TOOL)],
    cwd=ROOT,
    check=False,
)
assert compile_result.returncode == 0

print("Mail-domain inventory tooling validation passed")
print("No DNS, mailbox, provider, or routing changes are performed")
