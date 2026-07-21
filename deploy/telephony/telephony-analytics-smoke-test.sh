#!/bin/sh
set -eu

BASE_URL=${BASE_URL:-http://127.0.0.1:8098}

curl -fsS "$BASE_URL/healthz" | python3 -m json.tool
curl -fsS "$BASE_URL/api/telephony/platform/health" | python3 -m json.tool
curl -fsS "$BASE_URL/api/telephony/platform/calls/summary" | python3 -m json.tool
curl -fsS "$BASE_URL/api/telephony/platform/interconnects/summary" | python3 -m json.tool

code=$(curl -sS -o /tmp/wwcx-telephony-analytics-post.json -w '%{http_code}' -X POST "$BASE_URL/api/telephony/platform/health")
cat /tmp/wwcx-telephony-analytics-post.json
printf '\n'
[ "$code" = 405 ]

if ss -lnt | grep -E '0\.0\.0\.0:8098|\[::\]:8098' >/dev/null; then
  echo "ERROR: unsafe public listener detected on 8098" >&2
  exit 1
fi

echo "telephony analytics smoke test passed"
