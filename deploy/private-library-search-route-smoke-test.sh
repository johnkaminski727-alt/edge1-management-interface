#!/usr/bin/env bash
set -euo pipefail

# Smoke test for the VPN-only search route. Run on Edge1 (or a VPN peer,
# adjusting BIND_IP) after install-private-library-search-route.sh.
#
# Credentials: set EDGE1_SEARCH_ROUTE_CREDS="user:password" or the script
# prompts interactively.

BIND_IP="${1:-}"
ROUTE_PORT="${2:-8443}"

fail() {
  echo "ROUTE SMOKE TEST FAILED: $1" >&2
  exit 1
}

[ -n "$BIND_IP" ] || { echo "Usage: $0 <vpn-bind-ip> [port]" >&2; exit 1; }
BASE_URL="http://${BIND_IP}:${ROUTE_PORT}"

echo "1/5 unauthenticated request is rejected"
status="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${BASE_URL}/api/private-library/search?q=x&collection=operations")"
[ "$status" = "401" ] || fail "expected HTTP 401 without credentials, got ${status}"
echo "  HTTP 401 as expected"

if [ -z "${EDGE1_SEARCH_ROUTE_CREDS:-}" ]; then
  read -rp "Operator username: " ROUTE_USER
  read -rsp "Password: " ROUTE_PASS
  echo
  EDGE1_SEARCH_ROUTE_CREDS="${ROUTE_USER}:${ROUTE_PASS}"
fi

echo "2/5 authenticated search succeeds"
response="$(curl -fsS -u "$EDGE1_SEARCH_ROUTE_CREDS" --max-time 10 \
  "${BASE_URL}/api/private-library/search?q=VPN&collection=operations&limit=3")" \
  || fail "authenticated search request failed"
mode="$(echo "$response" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("mode",""))')" \
  || fail "authenticated search returned invalid JSON"
echo "  mode=${mode}"

echo "3/5 write methods are blocked at the route"
status="$(curl -s -o /dev/null -w '%{http_code}' -u "$EDGE1_SEARCH_ROUTE_CREDS" --max-time 10 \
  -X POST "${BASE_URL}/api/private-library/search")"
case "$status" in
  403|405) echo "  HTTP ${status} as expected" ;;
  *) fail "expected HTTP 403/405 for POST, got ${status}" ;;
esac

echo "4/5 wrapper port 8091 remains loopback-only"
if command -v ss >/dev/null 2>&1; then
  if ss -tln 'sport = :8091' | tail -n +2 | grep -vE '127\.0\.0\.1|\[::1\]' | grep -q ':8091'; then
    fail "port 8091 is listening beyond loopback"
  fi
  echo "  loopback only"
else
  echo "  ss not available; skipping"
fi

echo "5/5 route is not listening on a public/unspecified address"
if command -v ss >/dev/null 2>&1; then
  listeners="$(ss -tln "sport = :${ROUTE_PORT}" | tail -n +2)"
  echo "$listeners" | grep -qF "${BIND_IP}:${ROUTE_PORT}" || fail "route not listening on ${BIND_IP}:${ROUTE_PORT}"
  if echo "$listeners" | grep -E '0\.0\.0\.0:'"${ROUTE_PORT}"'|\[::\]:'"${ROUTE_PORT}" | grep -q .; then
    fail "route port ${ROUTE_PORT} is bound to all interfaces"
  fi
  echo "  bound to ${BIND_IP} only"
else
  echo "  ss not available; skipping"
fi

echo
echo "Route smoke test passed on ${BASE_URL} (search mode: ${mode})"
