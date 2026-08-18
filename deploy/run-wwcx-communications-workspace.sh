#!/bin/sh
set -eu

ROOT=${WWCX_COMMUNICATIONS_ROOT:-/opt/edge1-management-interface}
HOST=${WWCX_COMMUNICATIONS_HOST:-127.0.0.1}
PORT=${WWCX_COMMUNICATIONS_PORT:-8095}
SNAPSHOT=${WWCX_COMMUNICATIONS_EVENT_SNAPSHOT:-}

case "$HOST" in
  127.0.0.1|::1|localhost) ;;
  *)
    echo "refusing non-loopback WWCX_COMMUNICATIONS_HOST: $HOST" >&2
    exit 1
    ;;
esac

set -- /usr/bin/python3 "$ROOT/server/unified_communications_server.py" \
  --host "$HOST" \
  --port "$PORT"

if [ -n "$SNAPSHOT" ]; then
  set -- "$@" --event-snapshot "$SNAPSHOT"
fi

exec "$@"
