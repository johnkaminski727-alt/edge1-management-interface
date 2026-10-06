#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/opt/edge1-management-interface
CRED=/etc/credstore.encrypted/wwcx-openpgp-passphrase.cred
DROPIN=/etc/systemd/system/wwcx-openpgp-crypto.service.d/40-encrypted-credential.conf

if [[ ${1:-} != --apply ]]; then
    echo "Audit only. Use --apply after the encrypted credential exists."
    test -x "$ROOT/deploy/messaging/wwcx-openpgp-preset-passphrase.sh"
    if [[ -s "$CRED" ]]; then echo "credential_present=yes"; else echo "credential_present=no"; fi
    exit 0
fi

[[ $EUID -eq 0 ]] || { echo "--apply requires root" >&2; exit 1; }
[[ -s "$CRED" ]] || { echo "Encrypted credential missing: $CRED" >&2; exit 1; }

install -d -m 0755 /etc/systemd/system/wwcx-openpgp-crypto.service.d
cat > "$DROPIN" <<'UNIT'
[Service]
LoadCredentialEncrypted=wwcx-openpgp-passphrase:/etc/credstore.encrypted/wwcx-openpgp-passphrase.cred
ExecStartPre=/opt/edge1-management-interface/deploy/messaging/wwcx-openpgp-preset-passphrase.sh
UNIT
chmod 0644 "$DROPIN"
systemctl daemon-reload
systemctl restart wwcx-openpgp-crypto.service
sleep 1
systemctl is-active --quiet wwcx-openpgp-crypto.service

echo "Encrypted OpenPGP credential unlock installed."
