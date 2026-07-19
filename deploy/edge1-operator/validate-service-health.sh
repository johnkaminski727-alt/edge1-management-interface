#!/bin/sh
set -eu

SERVICE="edge1-operator.service"

if ! systemctl cat "$SERVICE" >/dev/null 2>&1; then
    echo "missing service: $SERVICE"
    exit 1
fi

state=$(systemctl is-enabled "$SERVICE" 2>/dev/null || true)
active=$(systemctl is-active "$SERVICE" 2>/dev/null || true)

printf 'service=%s\n' "$SERVICE"
printf 'enabled=%s\n' "$state"
printf 'active=%s\n' "$active"

if [ "$active" != "active" ]; then
    echo "service is not active"
    exit 1
fi

exit 0
