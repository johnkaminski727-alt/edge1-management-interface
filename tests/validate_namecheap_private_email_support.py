#!/usr/bin/env python3
"""Static and unit validation for Private Email support evidence intake."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
NORMALIZER = ROOT / "tools" / "messaging" / "normalize_namecheap_private_email_support.py"
TEST = ROOT / "tests" / "test_normalize_namecheap_private_email_support.py"
DOC = ROOT / "docs" / "messaging" / "namecheap-private-email-support-intake.md"
EXAMPLE = ROOT / "examples" / "messaging" / "namecheap-private-email-support-evidence.example.json"

for path in (NORMALIZER, TEST, DOC, EXAMPLE):
    assert path.is_file(), path
    assert path.stat().st_size > 500, path

example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
assert example["contract"] == "wwcx.namecheap-private-email-support-evidence.v1"
assert example["read_only"] is True
assert example["provider_family"] == "namecheap_private_email"
assert example["domain"] == "ww.cx"
assert all(value is False for value in example["completeness"].values())

normalizer_text = NORMALIZER.read_text(encoding="utf-8")
for required in (
    "offline and read-only",
    "SHA-256 mismatch",
    "secret-bearing field is prohibited",
    "refusing to normalize Private Email support evidence inside a Git working tree",
    '"provider_family": PROVIDER_FAMILY',
    '"method": "private_email_admin"',
    "Unproven boolean capabilities were normalized to false",
    "--strict-completeness",
):
    assert required in normalizer_text, required

for prohibited in (
    "requests.",
    "urllib.request",
    "http.client",
    "socket.",
    "subprocess.",
    "send_email",
    "add_forwarder",
    "delete_forwarder",
    "set_default_address",
    "passwd_pop",
):
    assert prohibited not in normalizer_text, prohibited

for secret_marker in (
    '"support_pin"',
    '"password"',
    '"api_token"',
    '"authorization"',
    '"cookie"',
    '"cpsess"',
    '"reset_link"',
    '"private_key"',
):
    assert secret_marker not in EXAMPLE.read_text(encoding="utf-8"), secret_marker

compile_result = subprocess.run(
    [sys.executable, "-m", "py_compile", str(NORMALIZER)],
    cwd=ROOT,
    check=False,
)
assert compile_result.returncode == 0

unit_result = subprocess.run(
    [
        sys.executable,
        "-m",
        "unittest",
        "tests.test_normalize_namecheap_private_email_support",
    ],
    cwd=ROOT,
    check=False,
)
assert unit_result.returncode == 0

print("Namecheap Private Email support evidence validation passed")
print("Support evidence is checksum-verified before parsing")
print("Secret-bearing fields are rejected")
print("Unproven capabilities fail closed")
print("Access classes are derived from canonical repository configuration")
print("No provider, mailbox, DNS, authentication, or mail-flow change is performed")
