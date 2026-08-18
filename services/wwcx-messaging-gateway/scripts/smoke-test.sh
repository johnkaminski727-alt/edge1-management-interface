#!/bin/sh
set -eu

BASE_URL="${BASE_URL:-http://127.0.0.1:58080}"
TOKEN="${WWCX_SIMULATOR_TOKEN:-test-token}"
READ_TOKEN="${WWCX_MANAGEMENT_READ_TOKEN:-test-read-token}"
EVENT_ID="11111111-1111-1111-1111-111111111111"
OUTBOUND_EVENT_ID="44444444-4444-4444-4444-444444444444"

curl -fsS "$BASE_URL/healthz"
curl -fsS "$BASE_URL/readyz"
curl -fsS "$BASE_URL/v1/management/status" \
  -H "x-wwcx-management-token: $READ_TOKEN" | grep -q '"service":"wwcx-messaging-gateway"'

payload='{"event_id":"'"$EVENT_ID"'","provider":"simulator","provider_event_id":"smoke-1","direction":"inbound","channel":"sms","from":"+16045550101","to":["+16045550102"],"text":"hello from smoke test","media":[]}'

first="$(curl -fsS -X POST "$BASE_URL/v1/simulator/messages" -H "content-type: application/json" -H "x-wwcx-simulator-token: $TOKEN" -d "$payload")"
second="$(curl -fsS -X POST "$BASE_URL/v1/simulator/messages" -H "content-type: application/json" -H "x-wwcx-simulator-token: $TOKEN" -d "$payload")"

printf '%s\n' "$first" | grep -q '"accepted":true'
printf '%s\n' "$second" | grep -q '"duplicate":true'
curl -fsS "$BASE_URL/v1/simulator/events/count" | grep -q '"count":1'

if [ "${WWCX_TEST_OUTBOUND_QUEUE:-0}" = "1" ]; then
  outbound_payload='{"event_id":"'"$OUTBOUND_EVENT_ID"'","provider":"simulator","provider_event_id":"smoke-out-1","direction":"outbound","channel":"sms","from":"+16045550101","to":["+16045550102"],"text":"queued outbound smoke test","media":[]}'
  queued="$(curl -fsS -X POST "$BASE_URL/v1/simulator/outbound" -H "content-type: application/json" -H "x-wwcx-simulator-token: $TOKEN" -d "$outbound_payload")"
  duplicate="$(curl -fsS -X POST "$BASE_URL/v1/simulator/outbound" -H "content-type: application/json" -H "x-wwcx-simulator-token: $TOKEN" -d "$outbound_payload")"
  printf '%s\n' "$queued" | grep -q '"queued":true'
  printf '%s\n' "$duplicate" | grep -q '"duplicate":true'
  curl -fsS "$BASE_URL/v1/management/outbound/queue" \
    -H "x-wwcx-management-token: $READ_TOKEN" | grep -q '"pending":1'
  worker="$(docker compose -f compose.test.yaml exec -T gateway python -m app.outbound_worker --once)"
  printf '%s\n' "$worker" | grep -q '"status": "sent"'
  curl -fsS "$BASE_URL/v1/management/outbound/queue" \
    -H "x-wwcx-management-token: $READ_TOKEN" | grep -q '"sent":1'
fi

printf 'WW.CX messaging gateway smoke test passed\n'
