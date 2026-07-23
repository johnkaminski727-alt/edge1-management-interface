#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "server/bitcoin_mining_readiness_exporter.py"
SERVICE = ROOT / "deploy/systemd/wwcx-bitcoin-mining-readiness.service"
TIMER = ROOT / "deploy/systemd/wwcx-bitcoin-mining-readiness.timer"
CONFIG = ROOT / "deploy/examples/bitcoin-mining-readiness.json"

for path in (EXPORTER, SERVICE, TIMER, CONFIG):
    if not path.is_file():
        raise SystemExit(f"Missing mining-readiness asset: {path.relative_to(ROOT)}")

source = EXPORTER.read_text(encoding="utf-8")
for marker in (
    '"format": "wwcx-bitcoin-mining-status-v1"',
    '"mining_enabled": enabled',
    '"address_exposed": False',
    'DEFAULT_OUTPUT = Path("/var/www/edge1-status/bitcoin-mining.json")',
    'os.replace(temporary, path)',
):
    if marker not in source:
        raise SystemExit(f"Missing mining-readiness marker: {marker}")

for forbidden in (
    "stratum+tcp://",
    "wallet_address",
    "private_key",
    "seed",
    "password",
    "api_token",
    "broadcast",
    "payto",
):
    if forbidden in source.lower():
        raise SystemExit(f"Sensitive or activating marker found: {forbidden}")

service = SERVICE.read_text(encoding="utf-8")
for marker in (
    "Type=oneshot",
    "User=electrum-watch",
    "ProtectSystem=strict",
    "NoNewPrivileges=true",
    "ReadWritePaths=/var/www/edge1-status",
    "ExecStart=/usr/bin/python3 /opt/wwcx-mining/libexec/bitcoin_mining_readiness_exporter.py",
    "ReadOnlyPaths=/etc/wwcx-mining /var/lib/wwcx-mining /opt/wwcx-mining",
):
    if marker not in service:
        raise SystemExit(f"Missing service hardening marker: {marker}")

print("Bitcoin mining readiness validation passed")
