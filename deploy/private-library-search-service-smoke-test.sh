#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-8091}"
BASE_URL="http://127.0.0.1:${PORT}"
REQUIRE_LIVE_DIRECT="${REQUIRE_LIVE_DIRECT:-0}"

fail() {
  echo "SMOKE TEST FAILED: $1" >&2
  exit 1
}

echo "1/4 service state"
systemctl is-active edge1-private-library-search.service >/dev/null 2>&1 \
  || fail "edge1-private-library-search.service is not active"
echo "  active"

echo "2/4 localhost-only binding"
if command -v ss >/dev/null 2>&1; then
  listeners="$(ss -tln "sport = :${PORT}" | tail -n +2)"
  [ -n "$listeners" ] || fail "nothing is listening on port ${PORT}"
  if echo "$listeners" | grep -vE '127\.0\.0\.1|\[::1\]' | grep -q ':'"${PORT}"; then
    fail "port ${PORT} is listening on a non-loopback address"
  fi
  echo "  loopback only"
else
  echo "  ss not available; skipping bind check"
fi

echo "3/4 search API responds"
response="$(curl -fsS --max-time 10 "${BASE_URL}/api/private-library/search?q=VPN&collection=operations&limit=3")" \
  || fail "search API request failed"
mode="$(echo "$response" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("mode",""))')" \
  || fail "search API returned invalid JSON"

if [ "$REQUIRE_LIVE_DIRECT" = "1" ] && [ "$mode" != "live_direct" ]; then
  fail "production validation requires mode=live_direct, got ${mode:-empty}"
fi

case "$mode" in
  live_direct) echo "  mode=live_direct (live library engine)" ;;
  live)        echo "  mode=live (HTTP backend)" ;;
  fixture|fixture_fallback)
    echo "  mode=${mode} (WARNING: not live; check library DB readability under the service)" ;;
  *) fail "unexpected search mode: ${mode}" ;;
esac

echo "4/4 disallowed collection rejected"
status="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
  "${BASE_URL}/api/private-library/search?q=x&collection=public")"
[ "$status" = "400" ] || fail "expected HTTP 400 for disallowed collection, got ${status}"
echo "  HTTP 400 as expected"

echo
echo "Smoke test passed on port ${PORT} (search mode: ${mode})"
