#!/bin/sh
set -eu

DATA_FILE=${EDGE1_TIME_AUTHORITY_OUTPUT:-/var/lib/edge1-time-authority/measurements.jsonl}
BASE_URL=${EDGE1_TIME_AUTHORITY_BASE_URL:-http://127.0.0.1:8092}
API_URL=${EDGE1_TIME_AUTHORITY_API_URL:-$BASE_URL/api/time-authority/summary?limit=200}
SYSTEMCTL_BIN=${EDGE1_TIME_AUTHORITY_SYSTEMCTL:-systemctl}

"$SYSTEMCTL_BIN" is-enabled --quiet edge1-time-authority-collector.timer
"$SYSTEMCTL_BIN" is-active --quiet edge1-time-authority-collector.timer
"$SYSTEMCTL_BIN" is-enabled --quiet edge1-time-authority-dashboard.service
"$SYSTEMCTL_BIN" is-active --quiet edge1-time-authority-dashboard.service
"$SYSTEMCTL_BIN" start edge1-time-authority-collector.service

test -s "$DATA_FILE"
curl -fsS "$BASE_URL/healthz" >/dev/null
curl -fsS "$API_URL" | python3 -c '
import json, sys
payload = json.load(sys.stdin)
assert payload.get("mode") == "live", payload.get("mode")
assert any(item.get("observer_id") == "edge1" for item in payload.get("latest", []))
'

echo "WW.CX Time Authority Edge1 smoke test passed."
