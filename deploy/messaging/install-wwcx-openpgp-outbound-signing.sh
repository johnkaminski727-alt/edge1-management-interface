#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
SERVICE=wwcx-outbound-mail-gateway.service
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
MODE="${1:-}"
HEAD="$(runuser -u wwadmin -- git -C "$ROOT" rev-parse --short HEAD)"
CURRENT_EXEC="$(systemctl show -p ExecStart --value "$SERVICE")"
CURRENT_RELEASE="$(printf '%s' "$CURRENT_EXEC" | sed -n 's#.*\(/opt/wwcx-email/releases/[^ /]*/server/outbound_mail_gateway_runtime_server.py\).*#\1#p' | sed 's#/server/outbound_mail_gateway_runtime_server.py##')"
NEW_RELEASE="/opt/wwcx-email/releases/${HEAD}-openpgp-signing"
DROPIN_DIR=/etc/systemd/system/wwcx-outbound-mail-gateway.service.d
DROPIN="$DROPIN_DIR/60-openpgp-signing-release.conf"
CONFIG_DIR=/etc/wwcx/outbound-mail
BACKUP="/var/backups/wwcx-openpgp-outbound-signing-$STAMP"
FILES=(
 server/identity_aware_outbound_gateway.py
 server/mail_secure_submission.py
 server/mail_openpgp_mime.py
 server/mail_openpgp_policy.py
 server/mail_openpgp_socket_adapter.py
 server/mail_openpgp_outbound_runtime.py
 server/outbound_mail_gateway_suppressed_server.py
 server/outbound_mail_gateway_runtime_server.py
)
[ -n "$CURRENT_RELEASE" ] && [ -d "$CURRENT_RELEASE" ] || { echo 'STOP: current release not resolved' >&2; exit 1; }
for f in "${FILES[@]}"; do [ -s "$ROOT/$f" ] || { echo "STOP: missing $f" >&2; exit 1; }; done
[ -s "$ROOT/config/messaging/openpgp-policy.json" ] || exit 1
[ -s "$ROOT/config/messaging/openpgp-outbound-senders.json" ] || exit 1
PYTHONPATH="$ROOT/server" python3 - <<'PY2'
import json
from mail_openpgp_policy import validate_policy
from mail_openpgp_outbound_runtime import validate_senders
validate_policy(json.load(open('/opt/edge1-management-interface/config/messaging/openpgp-policy.json')))
validate_senders(json.load(open('/opt/edge1-management-interface/config/messaging/openpgp-outbound-senders.json')))
print('OpenPGP runtime policy validation: PASS')
PY2
if [ "$MODE" != --apply ]; then
  echo "PASS: deployment preflight"
  echo "current_release=$CURRENT_RELEASE"
  echo "new_release=$NEW_RELEASE"
  exit 0
fi
[ "$(id -u)" -eq 0 ] || { echo 'STOP: --apply requires root' >&2; exit 1; }
mkdir -p "$BACKUP" "$DROPIN_DIR" "$CONFIG_DIR"
chmod 0700 "$BACKUP"
cp -a "$DROPIN" "$BACKUP/dropin.conf" 2>/dev/null || true
cp -a "$CONFIG_DIR/openpgp-policy.json" "$BACKUP/openpgp-policy.json" 2>/dev/null || true
cp -a "$CONFIG_DIR/openpgp-senders.json" "$BACKUP/openpgp-senders.json" 2>/dev/null || true
if [ ! -d "$NEW_RELEASE" ]; then cp -a "$CURRENT_RELEASE" "$NEW_RELEASE"; fi
for f in "${FILES[@]}"; do install -m 0644 "$ROOT/$f" "$NEW_RELEASE/$f"; done
install -o root -g wwcx-mail-gateway -m 0640 "$ROOT/config/messaging/openpgp-policy.json" "$CONFIG_DIR/openpgp-policy.json"
install -o root -g wwcx-mail-gateway -m 0640 "$ROOT/config/messaging/openpgp-outbound-senders.json" "$CONFIG_DIR/openpgp-senders.json"
cat > "$DROPIN" <<EOF
[Service]
WorkingDirectory=$NEW_RELEASE
ExecStart=
ExecStart=/usr/bin/python3 $NEW_RELEASE/server/outbound_mail_gateway_runtime_server.py --config /etc/wwcx/outbound-mail/gateway.json --identities /etc/wwcx/outbound-mail/identities.json --host 127.0.0.1 --port 8104
EOF
chmod 0644 "$DROPIN"
systemctl daemon-reload
systemctl restart "$SERVICE"
sleep 1
systemctl is-active --quiet "$SERVICE"
runuser -u wwcx-mail-gateway -- env PYTHONPATH="$NEW_RELEASE/server" python3 - <<'PY3'
from mail_openpgp_outbound_runtime import RuntimeOpenPGPResolver
r=RuntimeOpenPGPResolver()
out=r({'from_address':'john@ww.cx','recipients':['acceptance@example.net']})
assert out and out['operation']=='sign'
print('runtime_openpgp_resolver=PASS')
PY3
python3 - <<'PY4'
import json
cfg=json.load(open('/etc/wwcx/outbound-mail/gateway.json'))
ids=json.load(open('/etc/wwcx/outbound-mail/identities.json'))
assert cfg['enabled'] is False
assert cfg['external_delivery_authorized'] is False
assert cfg['admin']['send_endpoint_enabled'] is False
assert ids['outbound_activation_authorized'] is False
assert ids['sender_selection']['live_sender_allowlist']==[]
print('delivery_gates_remain_closed=PASS')
PY4
printf 'deployment=PASS\nrelease=%s\nbackup=%s\n' "$NEW_RELEASE" "$BACKUP"
