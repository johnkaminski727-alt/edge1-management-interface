#!/bin/sh
set -eu

BASE_URL="${BASE_URL:-http://127.0.0.1:58080}"
TOKEN="${WWCX_SIMULATOR_TOKEN:-test-token}"
READ_TOKEN="${WWCX_MANAGEMENT_READ_TOKEN:-test-read-token}"
EVENT_ID="11111111-1111-1111-1111-111111111111"
OUTBOUND_EVENT_ID="44444444-4444-4444-4444-444444444444"
STOP_EVENT_ID="55555555-5555-5555-5555-555555555555"
SUPPRESSED_OUTBOUND_ID="66666666-6666-6666-6666-666666666666"
HELP_EVENT_ID="77777777-7777-7777-7777-777777777777"
START_EVENT_ID="88888888-8888-8888-8888-888888888888"
STALE_STOP_EVENT_ID="99999999-9999-9999-9999-999999999999"
RESUMED_OUTBOUND_ID="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

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

  stop_payload='{"event_id":"'"$STOP_EVENT_ID"'","provider":"simulator","provider_event_id":"smoke-stop-1","direction":"inbound","channel":"sms","from":"+16045550103","to":["+16045550101"],"text":" STOP ","media":[],"occurred_at":"2026-08-18T23:00:00Z"}'
  curl -fsS -X POST "$BASE_URL/v1/simulator/messages" -H "content-type: application/json" -H "x-wwcx-simulator-token: $TOKEN" -d "$stop_payload" | grep -q '"accepted":true'
  compliance="$(curl -fsS "$BASE_URL/v1/management/compliance" -H "x-wwcx-management-token: $READ_TOKEN")"
  printf '%s\n' "$compliance" | grep -q '"keyword_suppression_count":1'
  printf '%s\n' "$compliance" | grep -q '"stop":1'

  suppressed_payload='{"event_id":"'"$SUPPRESSED_OUTBOUND_ID"'","provider":"simulator","provider_event_id":"smoke-out-suppressed-1","direction":"outbound","channel":"sms","from":"+16045550101","to":["+16045550103"],"text":"must not send while suppressed","media":[]}'
  curl -fsS -X POST "$BASE_URL/v1/simulator/outbound" -H "content-type: application/json" -H "x-wwcx-simulator-token: $TOKEN" -d "$suppressed_payload" | grep -q '"queued":true'
  worker="$(docker compose -f compose.test.yaml exec -T gateway python -m app.outbound_worker --once)"
  printf '%s\n' "$worker" | grep -q '"status": "suppressed"'

  help_payload='{"event_id":"'"$HELP_EVENT_ID"'","provider":"simulator","provider_event_id":"smoke-help-1","direction":"inbound","channel":"sms","from":"+16045550104","to":["+16045550101"],"text":"HELP","media":[],"occurred_at":"2026-08-18T23:00:30Z"}'
  curl -fsS -X POST "$BASE_URL/v1/simulator/messages" -H "content-type: application/json" -H "x-wwcx-simulator-token: $TOKEN" -d "$help_payload" | grep -q '"accepted":true'

  start_payload='{"event_id":"'"$START_EVENT_ID"'","provider":"simulator","provider_event_id":"smoke-start-1","direction":"inbound","channel":"sms","from":"+16045550103","to":["+16045550101"],"text":"START","media":[],"occurred_at":"2026-08-18T23:01:00Z"}'
  curl -fsS -X POST "$BASE_URL/v1/simulator/messages" -H "content-type: application/json" -H "x-wwcx-simulator-token: $TOKEN" -d "$start_payload" | grep -q '"accepted":true'

  stale_stop_payload='{"event_id":"'"$STALE_STOP_EVENT_ID"'","provider":"simulator","provider_event_id":"smoke-stop-stale-1","direction":"inbound","channel":"sms","from":"+16045550103","to":["+16045550101"],"text":"STOP","media":[],"occurred_at":"2026-08-18T22:59:00Z"}'
  curl -fsS -X POST "$BASE_URL/v1/simulator/messages" -H "content-type: application/json" -H "x-wwcx-simulator-token: $TOKEN" -d "$stale_stop_payload" | grep -q '"accepted":true'

  compliance="$(curl -fsS "$BASE_URL/v1/management/compliance" -H "x-wwcx-management-token: $READ_TOKEN")"
  printf '%s\n' "$compliance" | grep -q '"keyword_suppression_count":0'
  printf '%s\n' "$compliance" | grep -q '"help":1'
  printf '%s\n' "$compliance" | grep -q '"stale_event_count":1'
  printf '%s\n' "$compliance" | grep -q '"applied":false'

  resumed_payload='{"event_id":"'"$RESUMED_OUTBOUND_ID"'","provider":"simulator","provider_event_id":"smoke-out-resumed-1","direction":"outbound","channel":"sms","from":"+16045550101","to":["+16045550103"],"text":"send after START","media":[]}'
  curl -fsS -X POST "$BASE_URL/v1/simulator/outbound" -H "content-type: application/json" -H "x-wwcx-simulator-token: $TOKEN" -d "$resumed_payload" | grep -q '"queued":true'
  worker="$(docker compose -f compose.test.yaml exec -T gateway python -m app.outbound_worker --once)"
  printf '%s\n' "$worker" | grep -q '"status": "sent"'

  queue="$(curl -fsS "$BASE_URL/v1/management/outbound/queue" -H "x-wwcx-management-token: $READ_TOKEN")"
  printf '%s\n' "$queue" | grep -q '"sent":2'
  printf '%s\n' "$queue" | grep -q '"suppressed":1'
fi

printf 'WW.CX messaging gateway smoke test passed\n'
