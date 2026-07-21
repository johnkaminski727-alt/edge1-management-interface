#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "server/electrum_watch_api_server.py"
UNIT = ROOT / "deploy/systemd/edge1-electrum-watch-api.service"
CONFIG = ROOT / "deploy/configure-electrum-watch-api.sh"

for path in (API, UNIT, CONFIG):
    if not path.is_file():
        raise SystemExit(f"Missing Electrum watch API asset: {path.relative_to(ROOT)}")

source = API.read_text(encoding="utf-8")
required = [
    'ALLOWED_METHODS = {',
    '"/v1/wallet/info": "getinfo"',
    '"/v1/wallet/balance": "getbalance"',
    'def do_POST',
    '"error": "read_only"',
    'secrets.compare_digest',
    'args.host not in {"127.0.0.1", "localhost"}',
    'Cache-Control", "no-store"',
]
for marker in required:
    if marker not in source:
        raise SystemExit(f"Missing API safety marker: {marker}")

for forbidden in ("payto", "broadcast", "signtransaction", "getunusedaddress", "create_new_address"):
    if forbidden in source.lower():
        raise SystemExit(f"Mutating Electrum operation present: {forbidden}")

unit = UNIT.read_text(encoding="utf-8")
for marker in (
    "User=electrum-watch",
    "ExecStart=/usr/bin/python3 /opt/edge1-management-interface/server/electrum_watch_api_server.py --host 127.0.0.1 --port 8094",
    "NoNewPrivileges=true",
    "ProtectSystem=strict",
    "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6",
):
    if marker not in unit:
        raise SystemExit(f"Missing API unit hardening marker: {marker}")

config = CONFIG.read_text(encoding="utf-8")
for marker in (
    "secrets.token_urlsafe",
    'CONFIG_DIR="/etc/electrum-watch"',
    'CONFIG_FILE="$CONFIG_DIR/api.env"',
    'chmod 0640 "$CONFIG_FILE"',
):
    if marker not in config:
        raise SystemExit(f"Missing API configuration marker: {marker}")

print("Electrum watch-only API validation passed")
