#!/bin/sh
set -eu

BASE_URL="${BASE_URL:-http://127.0.0.1:58080}"
TOKEN="${WWCX_SIMULATOR_TOKEN:-test-token}"
READ_TOKEN="${WWCX_MANAGEMENT_READ_TOKEN:-test-read-token}"
PROVIDER_MESSAGE_ID="sim-44444444-4444-4444-4444-444444444444"

newer='{"provider":"simulator","provider_event_id":"smoke-dlr-delivered-1","provider_message_id":"'"$PROVIDER_MESSAGE_ID"'","status":"delivered","occurred_at":"2026-08-19T00:30:00Z","raw_status":"simulator-delivered"}'
stale='{"provider":"simulator","provider_event_id":"smoke-dlr-stale-1","provider_message_id":"'"$PROVIDER_MESSAGE_ID"'","status":"failed","occurred_at":"2026-08-19T00:29:00Z","raw_status":"simulator-failed-stale"}'

first="$(curl -fsS -X POST "$BASE_URL/v1/webhooks/simulator/delivery" -H "content-type: application/json" -H "x-wwcx-signature: $TOKEN" -d "$newer")"
replay="$(curl -fsS -X POST "$BASE_URL/v1/webhooks/simulator/delivery" -H "content-type: application/json" -H "x-wwcx-signature: $TOKEN" -d "$newer")"
older="$(curl -fsS -X POST "$BASE_URL/v1/webhooks/simulator/delivery" -H "content-type: application/json" -H "x-wwcx-signature: $TOKEN" -d "$stale")"

printf '%s\n' "$first" | grep -q '"accepted":true'
printf '%s\n' "$first" | grep -q '"applied":true'
printf '%s\n' "$first" | grep -q '"matched":true'
printf '%s\n' "$replay" | grep -q '"duplicate":true'
printf '%s\n' "$older" | grep -q '"accepted":true'
printf '%s\n' "$older" | grep -q '"applied":false'

status_json="$(curl -fsS "$BASE_URL/v1/management/delivery/status?limit=100" -H "x-wwcx-management-token: $READ_TOKEN")"
printf '%s\n' "$status_json" | grep -q '"durable":true'
printf '%s\n' "$status_json" | grep -q '"stale_event_count":1'
printf '%s\n' "$status_json" | grep -q '"unmatched_state_count":0'
printf '%s\n' "$status_json" | grep -q '"provider_message_id":"'"$PROVIDER_MESSAGE_ID"'"'
printf '%s\n' "$status_json" | grep -q '"status":"delivered"'

printf 'WW.CX delivery status smoke test passed\n'
