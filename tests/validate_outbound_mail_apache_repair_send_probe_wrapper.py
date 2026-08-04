#!/usr/bin/env python3
"""Validate the bounded wrapper that corrects the Apache repair send probe."""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "deploy/messaging/run-outbound-mail-apache-proxy-mapping-repair.sh"
ORIGINAL = ROOT / "deploy/messaging/repair-outbound-mail-phase-b2-apache-proxy-mapping.sh"

for path in (WRAPPER, ORIGINAL):
    assert path.is_file(), path

wrapper = WRAPPER.read_text(encoding="utf-8")
original = ORIGINAL.read_text(encoding="utf-8")

for required in (
    "set -eu",
    "umask 077",
    "mktemp",
    "trap cleanup EXIT HUP INT TERM",
    "expected exactly one legacy empty-object send probe",
    "apache-repair-canary@example.invalid",
    "business_correspondence",
    "confirm_send",
    "direct send response is not delivery_disabled",
    "GIT_OPTIONAL_LOCKS=0 sh \"$TEMPORARY\"",
):
    assert required in wrapper, required

for forbidden in (
    "WWCX_MAIL_GATEWAY_TOKEN=",
    "systemctl restart",
    "systemctl stop",
    "systemctl start",
    "nft add",
    "iptables -A",
    "ufw allow",
    "nsupdate",
):
    assert forbidden not in wrapper, forbidden

legacy = "  direct_send=$(curl -sS --max-time 5 -H 'Content-Type: application/json' -d '{}' -o /dev/null -w '%{http_code}' http://127.0.0.1:8104/outbound-mail/send || true)\n"
assert original.count(legacy) == 1
assert "apache-repair-canary@example.invalid" not in original
assert wrapper.count("apache-repair-canary@example.invalid") == 2
assert wrapper.count("delivery_disabled") >= 2

syntax = subprocess.run(["sh", "-n", str(WRAPPER)], cwd=ROOT, check=False)
assert syntax.returncode == 0

print("Outbound mail Apache repair send-probe wrapper validation passed")
print("The empty-object HTTP 400 probe is replaced by a valid disabled-send canary")
print("HTTP 403 and error=delivery_disabled are both required")
print("Credentials, provider activation, delivery, and message traffic remain blocked")
