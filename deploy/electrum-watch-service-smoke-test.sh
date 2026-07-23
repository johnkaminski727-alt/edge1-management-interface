#!/usr/bin/env bash
set -euo pipefail

SERVICE="edge1-electrum-watch.service"
RPC_ENV="/etc/electrum-watch/rpc.env"
WALLET="/var/lib/electrum-watch/wallets/wwcx-watch-only"
ELECTRUM="/opt/electrum-watch/bin/electrum"

if [ "${EUID}" -ne 0 ]; then
  echo "electrum-watch-service-smoke-test.sh must run as root" >&2
  exit 1
fi

systemctl is-active --quiet "$SERVICE"
test -x "$ELECTRUM"
test -f "$WALLET"
test -f "$RPC_ENV"

# shellcheck disable=SC1090
. "$RPC_ENV"

case "$ELECTRUM_RPC_HOST" in
  127.0.0.1|localhost) ;;
  *) echo "RPC host is not localhost: $ELECTRUM_RPC_HOST" >&2; exit 1 ;;
esac

RPC_RESULT="$(curl --fail --silent --show-error \
  --user "$ELECTRUM_RPC_USER:$ELECTRUM_RPC_PASSWORD" \
  --header 'Content-Type: application/json' \
  --data-binary '{"jsonrpc":"2.0","id":"edge1-smoke","method":"getinfo","params":[]}' \
  "http://$ELECTRUM_RPC_HOST:$ELECTRUM_RPC_PORT")"

python3 - "$RPC_RESULT" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
if payload.get("id") != "edge1-smoke":
    raise SystemExit("Unexpected JSON-RPC response id")
if payload.get("error"):
    raise SystemExit("Electrum JSON-RPC returned an error")
if "result" not in payload:
    raise SystemExit("Electrum JSON-RPC response has no result")
print("Electrum JSON-RPC health check passed")
PY

WALLET_INFO="$(sudo -u electrum-watch env HOME=/var/lib/electrum-watch ELECTRUMDIR=/var/lib/electrum-watch/.electrum \
  "$ELECTRUM" -w "$WALLET" getinfo)"
python3 - "$WALLET_INFO" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
if not isinstance(payload, dict):
    raise SystemExit("Unexpected wallet info response")
print("Electrum watch-only wallet command passed")
PY

if command -v ss >/dev/null 2>&1; then
  if ss -lntH "sport = :$ELECTRUM_RPC_PORT" | awk '{print $4}' | grep -Ev '^(127\.0\.0\.1|\[::1\]):' >/dev/null; then
    echo "Electrum RPC is listening on a non-loopback address" >&2
    exit 1
  fi
fi

echo "Electrum watch-only service smoke test passed"
