#!/usr/bin/env python3
"""Repository validation for provider mail-object reconciliation tooling."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "messaging"
RECONCILER = TOOLS / "reconcile_mail_provider_objects.py"
CAPTURE = TOOLS / "capture_cpanel_mail_inventory.sh"
SCHEMA = ROOT / "schemas" / "messaging" / "mail-provider-objects.schema.json"
EXAMPLE = ROOT / "examples" / "messaging" / "mail-provider-objects.example.json"
DOC = ROOT / "docs" / "messaging" / "provider-object-reconciliation.md"
INBOUND = ROOT / "config" / "messaging" / "inbound-mail-hub.json"
IDENTITIES = ROOT / "config" / "messaging" / "mail-identities.json"

sys.path.insert(0, str(TOOLS))

import reconcile_mail_provider_objects

for path in (RECONCILER, CAPTURE, SCHEMA, EXAMPLE, DOC, INBOUND, IDENTITIES):
    assert path.is_file(), path
    assert path.stat().st_size > 100, path

schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
inbound = json.loads(INBOUND.read_text(encoding="utf-8"))
identities = json.loads(IDENTITIES.read_text(encoding="utf-8"))

assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
assert schema["properties"]["contract"]["const"] == "wwcx.provider-mail-objects.v1"
assert example["source"]["read_only"] is True
normalized = reconcile_mail_provider_objects.validate_inventory(example)
assert normalized["provider_id"] == "example-namecheap-shared-hosting"

report = reconcile_mail_provider_objects.reconcile(inbound, identities, [example])
assert report["contract"] == "wwcx.provider-mail-reconciliation.v1"
assert report["read_only"] is True
assert report["summary"]["expected_route_count"] == 37
assert report["summary"]["critical_gap_count"] > 0
assert report["summary"]["ready_for_pilot"] is False
assert any(
    warning["type"] == "unexpected_managed_addresses"
    for warning in report["warnings"]
)

capture_text = CAPTURE.read_text(encoding="utf-8")
for required in (
    "Email list_mail_domains",
    "Email list_pops",
    "Email list_domain_forwarders",
    "Email list_forwarders",
    "Email list_default_address",
    "Email list_auto_responders",
    "Email list_filters",
    "Refusing to store provider evidence inside Git working tree",
    "restricted operational metadata",
    "sha256sum",
    "CURRENT_UID=$(id -u)",
    "CURRENT_USER=$(id -un)",
    "only root may specify the CLI --user option",
    'uapi --output=jsonpretty "$@"',
    'uapi --output=jsonpretty "--user=$CPANEL_USER" "$@"',
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
    [
        sys.executable,
        "-m",
        "unittest",
        "tests.test_reconcile_mail_provider_objects",
        "tests.test_capture_cpanel_mail_inventory",
    ],
    cwd=ROOT,
    check=False,
)
assert unit_result.returncode == 0

compile_result = subprocess.run(
    [sys.executable, "-m", "py_compile", str(RECONCILER)],
    cwd=ROOT,
    check=False,
)
assert compile_result.returncode == 0

with tempfile.TemporaryDirectory() as temp_dir:
    output = pathlib.Path(temp_dir) / "report.json"
    cli_result = subprocess.run(
        [
            sys.executable,
            str(RECONCILER),
            "--inventory",
            str(EXAMPLE),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
    )
    assert cli_result.returncode == 0
    cli_report = json.loads(output.read_text(encoding="utf-8"))
    assert cli_report["summary"]["expected_route_count"] == 37
    strict_result = subprocess.run(
        [
            sys.executable,
            str(RECONCILER),
            "--inventory",
            str(EXAMPLE),
            "--strict",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        check=False,
    )
    assert strict_result.returncode == 2

print("Provider mail-object reconciliation validation passed")
print("cPanel capture script uses read-only UAPI operations only")
print("Normal cPanel account shells omit the root-only UAPI --user option")
print("Normalized inventories are checked against all 37 canonical routes")
print("No provider, mailbox, forwarding, DNS, or delivery change is performed")
