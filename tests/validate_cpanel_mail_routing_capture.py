#!/usr/bin/env python3
"""Static and unit validation for cPanel mail-routing evidence tooling."""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "tools" / "messaging" / "capture_cpanel_mail_routing.ps1"
NORMALIZER = ROOT / "tools" / "messaging" / "normalize_cpanel_mail_routing.py"
DOC = ROOT / "docs" / "messaging" / "cpanel-mail-routing-capture.md"

for path in (CAPTURE, NORMALIZER, DOC):
    assert path.is_file(), path
    assert path.stat().st_size > 500, path

capture_text = CAPTURE.read_text(encoding="utf-8")
for required in (
    "cpanel_jsonapi_apiversion = '2'",
    "cpanel_jsonapi_module     = 'Email'",
    "cpanel_jsonapi_func       = 'getmxcheck'",
    "Authorization = ('cpanel {0}:{1}'",
    "wwcx.cpanel-mail-routing-evidence.v1",
    "Email::getmxcheck",
    "SHA256SUMS",
    "ZeroFreeBSTR",
    "Refusing to store provider routing evidence inside a Git working tree",
):
    assert required in capture_text, required

for prohibited in (
    "setmxcheck",
    "setalwaysaccept",
    "add_mx",
    "change_mx",
    "delete_mx",
    "add_forwarder",
    "delete_forwarder",
    "set_default_address",
):
    assert prohibited not in capture_text, prohibited

normalizer_text = NORMALIZER.read_text(encoding="utf-8")
for required in (
    "offline and read-only",
    "SHA-256 mismatch",
    "Email::getmxcheck",
    '"method": "provider_api"',
    '"provider_family": "namecheap_shared_hosting"',
    '"secondary": "unknown"',
):
    assert required in normalizer_text, required

for prohibited in (
    "requests.",
    "urllib.request",
    "http.client",
    "socket.",
    "subprocess.",
    "setmxcheck",
):
    assert prohibited not in normalizer_text, prohibited

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
        "tests.test_normalize_cpanel_mail_routing",
    ],
    cwd=ROOT,
    check=False,
)
assert unit_result.returncode == 0

print("cPanel mail-routing evidence validation passed")
print("Capture is restricted to deprecated read-only Email::getmxcheck")
print("Temporary API-token material is not written to evidence")
print("Routing evidence is checksum-verified and normalized offline")
print("No cPanel mail-routing, DNS, mailbox, or forwarding mutation is performed")
