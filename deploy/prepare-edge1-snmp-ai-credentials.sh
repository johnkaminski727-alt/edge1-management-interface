#!/bin/sh
set -eu
SOURCE=${EDGE1_BIGBIRD_ENV:-/etc/bigbird-ai-gateway.env}
DEST=${EDGE1_SNMP_AI_CREDENTIAL_SOURCE_DIR:-/run/edge1-snmp-ai-identity}

if [ ! -f "$SOURCE" ]; then
    printf '%s\n' "Missing BigBird gateway environment file: $SOURCE" >&2
    exit 1
fi
if [ ! -r "$SOURCE" ]; then
    printf '%s\n' "BigBird gateway environment file is not readable by credential projector" >&2
    exit 1
fi

set -a
# The canonical file is root-owned and is already consumed as a systemd EnvironmentFile.
# Source it only inside this root-only one-shot, then project the two relay values needed
# by the SNMP API into transient systemd credential sources under /run.
. "$SOURCE"
set +a

if [ -z "${BB_RELAY_KEY_ID:-}" ]; then
    printf '%s\n' "BB_RELAY_KEY_ID is not configured in the canonical BigBird environment" >&2
    exit 1
fi
if [ -z "${BB_RELAY_SECRET:-}" ] || [ "${#BB_RELAY_SECRET}" -lt 32 ]; then
    printf '%s\n' "BB_RELAY_SECRET is missing or invalid in the canonical BigBird environment" >&2
    exit 1
fi

install -d -o root -g root -m 0700 "$DEST"
umask 077
key_tmp=$(mktemp "$DEST/.key.XXXXXX")
secret_tmp=$(mktemp "$DEST/.secret.XXXXXX")
trap 'rm -f "$key_tmp" "$secret_tmp"' EXIT HUP INT TERM

printf '%s' "$BB_RELAY_KEY_ID" > "$key_tmp"
printf '%s' "$BB_RELAY_SECRET" > "$secret_tmp"
chown root:root "$key_tmp" "$secret_tmp"
chmod 0600 "$key_tmp" "$secret_tmp"
mv -f "$key_tmp" "$DEST/bb_relay_key_id"
mv -f "$secret_tmp" "$DEST/bb_relay_secret"
trap - EXIT HUP INT TERM

printf '%s\n' "Prepared scoped SNMP AI runtime credentials in $DEST"
