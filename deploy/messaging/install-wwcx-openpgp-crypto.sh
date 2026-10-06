#!/bin/sh
set -eu
[ "$(id -u)" -eq 0 ] || { echo 'root required' >&2; exit 1; }
REPO=${REPO_ROOT:-/opt/edge1-management-interface}
getent group wwcx-mail-gateway >/dev/null
if ! getent passwd wwcx-openpgp >/dev/null; then
  useradd --system --home-dir /var/lib/wwcx-openpgp --shell /usr/sbin/nologin --gid wwcx-mail-gateway wwcx-openpgp
fi
install -d -o wwcx-openpgp -g wwcx-mail-gateway -m 0750 /var/lib/wwcx-openpgp
install -d -o wwcx-openpgp -g wwcx-mail-gateway -m 0700 /var/lib/wwcx-openpgp/gnupg
install -d -o root -g root -m 0755 /etc/wwcx
install -o root -g wwcx-mail-gateway -m 0640 "$REPO/config/messaging/openpgp-crypto-service.json" /etc/wwcx/openpgp-service.json
install -o root -g root -m 0644 "$REPO/deploy/messaging/wwcx-openpgp-crypto.service" /etc/systemd/system/wwcx-openpgp-crypto.service
systemctl daemon-reload
systemctl enable --now wwcx-openpgp-crypto.service
systemctl is-active --quiet wwcx-openpgp-crypto.service
# Safe stage must have no secret keys and all operations disabled.
python3 - <<'PY'
import json,socket
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.connect('/run/wwcx-openpgp/crypto.sock');s.sendall(b'{"operation":"status"}\n');r=json.loads(s.makefile().readline());
assert r['ok'] and r['result']['secret_key_count']==0
assert not r['result']['encrypt_enabled'] and not r['result']['decrypt_enabled'] and not r['result']['sign_enabled']
assert r['result']['private_key_export_supported'] is False
PY
echo 'WW.CX OpenPGP crypto service installed safe-disabled'
