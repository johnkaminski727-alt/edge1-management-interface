#!/usr/bin/env python3
"""Validate the runtime-migration state-write-boundary wrapper."""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "deploy/messaging/install-outbound-mail-disabled-runtime-migration-fixed.sh"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


check(WRAPPER.is_file(), f"missing {WRAPPER}")
check(WRAPPER.stat().st_size > 500, f"undersized {WRAPPER}")
check(subprocess.run(["sh", "-n", str(WRAPPER)], check=False).returncode == 0, "wrapper shell syntax failed")

source = WRAPPER.read_text(encoding="utf-8")
for required in (
    "ReadWritePaths=$STATE_ROOT",
    "service_blocks",
    "unexpected systemd drop-in template",
    "Original installer already contains",
    "mktemp /tmp/wwcx-outbound-mail-runtime-migration",
    "trap cleanup EXIT HUP INT TERM",
    "sh -n",
    'sh "$temporary"',
):
    check(required in source, f"wrapper missing safety marker: {required}")

for prohibited in (
    "curl -k",
    "--insecure",
    "rm -rf",
    "sudo ",
    "systemctl ",
    "iptables",
    "nft ",
    "ufw ",
    "certbot",
    "WWCX_MAIL_SMTP_PASSWORD",
    "WWCX_MAIL_SMTP_USERNAME",
):
    check(prohibited not in source, f"wrapper contains prohibited operation: {prohibited}")

with tempfile.TemporaryDirectory() as temporary_dir:
    root = pathlib.Path(temporary_dir)
    original = root / "original.sh"
    original.write_text(
        """#!/bin/sh
set -eu
STATE_ROOT=${STATE_ROOT:-/var/lib/wwcx-outbound-mail}
write_dropin() {
cat <<EOF
[Service]
ExecStart=/bin/true
EOF
}
write_dropin
""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update({"REPO": str(root), "ORIGINAL": str(original)})
    result = subprocess.run(["sh", str(WRAPPER)], env=env, text=True, capture_output=True, check=False)
    check(result.returncode == 0, f"wrapper transform failed: {result.stderr}")
    check(result.stdout.count("ReadWritePaths=/var/lib/wwcx-outbound-mail") == 1, "state root was not injected exactly once")
    check("ExecStart=/bin/true" in result.stdout, "original drop-in content was not preserved")

    original.write_text("#!/bin/sh\n[Service]\n[Service]\n", encoding="utf-8")
    result = subprocess.run(["sh", str(WRAPPER)], env=env, text=True, capture_output=True, check=False)
    check(result.returncode != 0, "wrapper accepted multiple service blocks")

    original.write_text("#!/bin/sh\n[Service]\nReadWritePaths=$STATE_ROOT\n", encoding="utf-8")
    result = subprocess.run(["sh", str(WRAPPER)], env=env, text=True, capture_output=True, check=False)
    check(result.returncode != 0, "wrapper accepted an already-patched installer")

print("Runtime migration state-write-boundary wrapper validation passed")
print("Exactly one systemd service block is patched and the original installer gates remain authoritative")
