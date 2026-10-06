#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
OUT=/etc/wwcx/outbound-mail/openpgp-recipient-keys.json
MODE="${1:-}"
TMP="$(mktemp /tmp/wwcx-openpgp-recipient-map.XXXXXX.json)"
trap 'rm -f "$TMP"' EXIT
"$ROOT/tools/messaging/export_openpgp_recipient_keys.py" --output "$TMP"
python3 - "$TMP" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x['contract']=='wwcx.openpgp-recipient-keys.v1'
assert x['private_key_material_included'] is False
assert x['armored_public_key_material_included'] is False
print('recipient_map_count='+str(len(x['recipients'])))
PY
if [ "$MODE" != --apply ]; then
  echo 'PASS: recipient-map preflight'
  exit 0
fi
[ "$(id -u)" -eq 0 ] || { echo 'STOP: --apply requires root' >&2; exit 1; }
install -d -o root -g wwcx-mail-gateway -m 0750 /etc/wwcx/outbound-mail
if [ -f "$OUT" ]; then
  STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  install -d -m 0700 "/var/backups/wwcx-openpgp-recipient-map-$STAMP"
  cp -a "$OUT" "/var/backups/wwcx-openpgp-recipient-map-$STAMP/openpgp-recipient-keys.json"
fi
install -o root -g wwcx-mail-gateway -m 0640 "$TMP" "$OUT"
runuser -u wwcx-mail-gateway -- python3 - "$OUT" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
assert x['private_key_material_included'] is False
assert x['armored_public_key_material_included'] is False
print('runtime_recipient_map_readable=PASS')
PY
echo 'recipient_map_install=PASS'
