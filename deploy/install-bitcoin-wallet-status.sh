#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_ROOT="/opt/electrum-watch/libexec"
SYSTEMD_ROOT="/etc/systemd/system"
STATUS_ROOT="/var/www/edge1-status"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

install -d -m 0755 -o root -g root "$INSTALL_ROOT"
install -d -m 0755 -o electrum-watch -g electrum-watch "$STATUS_ROOT"
install -m 0755 -o root -g root \
  "$REPO_ROOT/server/electrum_wallet_status_exporter.py" \
  "$INSTALL_ROOT/electrum_wallet_status_exporter.py"
install -m 0644 -o root -g root \
  "$REPO_ROOT/deploy/systemd/wwcx-bitcoin-wallet-status.service" \
  "$SYSTEMD_ROOT/wwcx-bitcoin-wallet-status.service"
install -m 0644 -o root -g root \
  "$REPO_ROOT/deploy/systemd/wwcx-bitcoin-wallet-status.timer" \
  "$SYSTEMD_ROOT/wwcx-bitcoin-wallet-status.timer"

systemctl daemon-reload
systemctl enable --now wwcx-bitcoin-wallet-status.timer
systemctl start wwcx-bitcoin-wallet-status.service || true

python3 - <<'PY'
import json
from pathlib import Path

path = Path('/var/www/edge1-status/bitcoin-wallet.json')
if not path.is_file():
    raise SystemExit('wallet status document was not created')

raw = path.read_text(encoding='utf-8')
data = json.loads(raw)
if data.get('format') != 'wwcx-bitcoin-wallet-status-v1':
    raise SystemExit('wallet status format is invalid')

wallet = data.get('wallet') or {}
if wallet.get('type') != 'watch-only' or wallet.get('private_keys_enabled') is not False:
    raise SystemExit('wallet status security boundary is invalid')

for forbidden_key in ('address', 'descriptor', 'xpub', 'seed', 'token', 'password'):
    if forbidden_key in raw.lower():
        raise SystemExit('wallet status document contains forbidden field: ' + forbidden_key)

for key in wallet:
    if key.startswith('private_key') and key != 'private_keys_enabled':
        raise SystemExit('wallet status document contains forbidden private-key field')

print('Bitcoin wallet status exporter installation passed')
PY
