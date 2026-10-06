#!/usr/bin/env bash
set -Eeuo pipefail

GNUPGHOME=/var/lib/wwcx-openpgp/gnupg
export GNUPGHOME
CRED_NAME=wwcx-openpgp-passphrase
PRESET=/usr/lib/gnupg/gpg-preset-passphrase

: "${CREDENTIALS_DIRECTORY:?systemd credentials directory is unavailable}"
CRED="$CREDENTIALS_DIRECTORY/$CRED_NAME"

if [[ ! -r "$CRED" ]]; then
    echo "OpenPGP credential is unavailable" >&2
    exit 1
fi

install -d -m 0700 "$GNUPGHOME"

CONF="$GNUPGHOME/gpg-agent.conf"
if ! grep -qxF 'allow-preset-passphrase' "$CONF" 2>/dev/null; then
    printf '%s\n' 'allow-preset-passphrase' >> "$CONF"
fi
if ! grep -qxF 'max-cache-ttl 31536000' "$CONF" 2>/dev/null; then
    printf '%s\n' 'max-cache-ttl 31536000' >> "$CONF"
fi
chmod 0600 "$CONF"

gpgconf --homedir "$GNUPGHOME" --kill gpg-agent >/dev/null 2>&1 || true
gpgconf --homedir "$GNUPGHOME" --launch gpg-agent >/dev/null

mapfile -t KEYGRIPS < <(
python3 - <<'PY'
import subprocess
p=subprocess.run([
    'gpg','--batch','--with-colons','--with-keygrip',
    '--homedir','/var/lib/wwcx-openpgp/gnupg',
    '--list-secret-keys','john@ww.cx'
],capture_output=True,text=True,check=True)
want=False
for line in p.stdout.splitlines():
    f=line.split(':')
    if f[0]=='ssb':
        caps=f[11] if len(f)>11 else ''
        want=('s' in caps.lower() or 'e' in caps.lower())
    elif f[0]=='grp' and want and len(f)>9 and f[9]:
        print(f[9])
        want=False
PY
)

if [[ ${#KEYGRIPS[@]} -lt 2 ]]; then
    echo "Expected signing and encryption secret subkey keygrips" >&2
    exit 1
fi

for grip in "${KEYGRIPS[@]}"; do
    "$PRESET" --preset "$grip" < "$CRED"
done

# Do not print keygrips or credential material.
echo "OpenPGP operational subkeys unlocked in gpg-agent cache."
