#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/edge1_sha256_benchmark.py"
SERVICE = ROOT / "deploy/systemd/wwcx-edge1-sha256-benchmark.service"

for path in (SCRIPT, SERVICE):
    if not path.is_file():
        raise SystemExit("Missing benchmark asset: %s" % path.relative_to(ROOT))

source = SCRIPT.read_text(encoding="utf-8")
for marker in (
    "hashlib.sha256(hashlib.sha256",
    '"benchmark": True',
    '"pool_connected": False',
    '"unpaid_btc": "0.00000000"',
    "seconds must be between 10 and 300",
):
    if marker not in source:
        raise SystemExit("Missing benchmark marker: %s" % marker)

for forbidden in (
    "socket",
    "urllib",
    "requests",
    "stratum",
    "wallet_address",
    "private_key",
    "seed phrase",
    "password",
    "api_token",
    "broadcast",
    "payto",
):
    if forbidden in source.lower():
        raise SystemExit("Forbidden benchmark capability: %s" % forbidden)

service = SERVICE.read_text(encoding="utf-8")
for marker in (
    "Type=oneshot",
    "Nice=19",
    "IOSchedulingClass=idle",
    "CPUQuota=10%",
    "RestrictAddressFamilies=AF_UNIX",
    "NoNewPrivileges=true",
    "--seconds 120",
):
    if marker not in service:
        raise SystemExit("Missing service safety marker: %s" % marker)

print("Edge1 SHA-256 benchmark validation passed")
