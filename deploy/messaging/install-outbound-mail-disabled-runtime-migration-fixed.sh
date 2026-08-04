#!/bin/sh
set -eu
umask 077

REPO=${REPO:-/opt/edge1-management-interface}
ORIGINAL=${ORIGINAL:-$REPO/deploy/messaging/install-outbound-mail-disabled-runtime-migration.sh}

[ -f "$ORIGINAL" ] && [ ! -L "$ORIGINAL" ] || {
    echo "Original runtime migration installer is absent or unsafe: $ORIGINAL" >&2
    exit 1
}

service_blocks=$(awk '$0 == "[Service]" { count += 1 } END { print count + 0 }' "$ORIGINAL")
[ "$service_blocks" -eq 1 ] || {
    echo "Original installer has an unexpected systemd drop-in template." >&2
    exit 1
}

if grep -Fq 'ReadWritePaths=$STATE_ROOT' "$ORIGINAL"; then
    echo "Original installer already contains the runtime state write boundary; use it directly." >&2
    exit 1
fi

temporary=$(mktemp /tmp/wwcx-outbound-mail-runtime-migration.XXXXXX.sh)
cleanup() {
    rm -f "$temporary"
}
trap cleanup EXIT HUP INT TERM

sed '/^\[Service\]$/a ReadWritePaths=$STATE_ROOT' "$ORIGINAL" > "$temporary"
chmod 0700 "$temporary"
sh -n "$temporary"

grep -Fqx 'ReadWritePaths=$STATE_ROOT' "$temporary" || {
    echo "Failed to inject the runtime state write boundary." >&2
    exit 1
}

GIT_OPTIONAL_LOCKS=0 sh "$temporary"
