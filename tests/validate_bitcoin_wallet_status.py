#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "server/electrum_wallet_status_exporter.py"
SERVICE = ROOT / "deploy/systemd/wwcx-bitcoin-wallet-status.service"
TIMER = ROOT / "deploy/systemd/wwcx-bitcoin-wallet-status.timer"
API = ROOT / "server/electrum_watch_api_server.py"

for path in (EXPORTER, SERVICE, TIMER, API):
    if not path.is_file():
        raise SystemExit(f"Missing wallet-status asset: {path.relative_to(ROOT)}")

source = EXPORTER.read_text(encoding="utf-8")
for marker in (
    '"format": "wwcx-bitcoin-wallet-status-v1"',
    '"private_keys_enabled": False',
    '"type": "watch-only"',
    '"loaded": loaded',
    'http://127.0.0.1:8094',
    '/v1/wallet/info',
    '/v1/wallet/balance',
    '/v1/wallet/state',
    'os.replace(temporary, path)',
):
    if marker not in source:
        raise SystemExit(f"Missing exporter marker: {marker}")

for forbidden in (
    "payto",
    "broadcast",
    "signtransaction",
    "getunusedaddress",
):
    if forbidden in source.lower():
        raise SystemExit(f"Mutating wallet operation found: {forbidden}")

service = SERVICE.read_text(encoding="utf-8")
for marker in (
    "User=electrum-watch",
    "ProtectSystem=strict",
    "NoNewPrivileges=true",
    "ReadWritePaths=/var/www/edge1-status",
):
    if marker not in service:
        raise SystemExit(f"Missing service hardening marker: {marker}")

api = API.read_text(encoding="utf-8")
for marker in (
    '.encode("utf-8")',
    "secrets.compare_digest",
    'electrum_rpc("list_wallets")',
    '"/v1/wallet/state"',
    '"loaded": bool(wallets)',
    '"synchronized": synchronized',
):
    if marker not in api:
        raise SystemExit(f"Missing sanitized wallet-state marker: {marker}")

for forbidden in (
    '"path"',
    '"unlocked"',
    '"wallet_path"',
):
    if forbidden in api:
        raise SystemExit(f"Wallet-identifying state exposed by API: {forbidden}")

print("Bitcoin watch-only wallet status validation passed")
