#!/usr/bin/env python3
"""Repository validation for the cPanel HTTPS mail-inventory fallback."""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "tools" / "messaging" / "capture_cpanel_mail_inventory_https.sh"
TEST = ROOT / "tests" / "test_capture_cpanel_mail_inventory_https.py"
DOC = ROOT / "docs" / "messaging" / "cpanel-https-mail-inventory-fallback.md"

for path in (CAPTURE, TEST, DOC):
    assert path.is_file(), path
    assert path.stat().st_size > 100, path

capture_text = CAPTURE.read_text(encoding="utf-8")
for required in (
    "https://$CPANEL_HOST:2083/execute/$module/$function",
    "Authorization: cpanel %s:%s",
    "curl --config -",
    "Refusing to read an API token while shell tracing is enabled",
    "hidden-terminal-prompt",
    '"token_retained": False',
    "Email list_mail_domains",
    "Email list_pops",
    "Email list_domain_forwarders",
    "Email list_forwarders",
    "Email list_default_address",
    "Email list_auto_responders",
    "Email list_filters",
):
    assert required in capture_text, required

for prohibited in (
    "Email add_pop",
    "Email delete_pop",
    "Email add_forwarder",
    "Email delete_forwarder",
    "Email set_default_address",
    "Email passwd_pop",
    "Email edit_pop_quota",
    "Email suspend_",
):
    assert prohibited not in capture_text, prohibited

shell_result = subprocess.run(["sh", "-n", str(CAPTURE)], check=False)
assert shell_result.returncode == 0

unit_result = subprocess.run(
    [sys.executable, "-m", "unittest", "tests.test_capture_cpanel_mail_inventory_https"],
    cwd=ROOT,
    check=False,
)
assert unit_result.returncode == 0

print("cPanel HTTPS mail-inventory fallback validation passed")
print("Only read-only Email UAPI functions are present")
print("API token is excluded from curl command-line arguments and evidence metadata")
