#!/bin/sh
set -eu

BASE_URL="${BASE_URL:-http://127.0.0.1:58080}"
TOKEN="${WWCX_SIMULATOR_TOKEN:-test-token}"
READ_TOKEN="${WWCX_MANAGEMENT_READ_TOKEN:-test-read-token}"
EVENT_ID="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

payload='{"event_id":"'"$EVENT_ID"'","provider":"simulator","provider_event_id":"smoke-webhook-receipt-1","direction":"inbound","channel":"sms","from":"+16045550110","to":["+16045550101"],"text":"durable webhook receipt smoke","media":[]}'

first="$(curl -fsS -X POST "$BASE_URL/v1/webhooks/simulator" -H "content-type: application/json" -H "x-wwcx-signature: $TOKEN" -d "$payload")"
second="$(curl -fsS -X POST "$BASE_URL/v1/webhooks/simulator" -H "content-type: application/json" -H "x-wwcx-signature: $TOKEN" -d "$payload")"

printf '%s\n' "$first" | grep -q '"accepted":true'
printf '%s\n' "$second" | grep -q '"duplicate":true'
printf '%s\n' "$first" | grep -q '"receipt_id"'
printf '%s\n' "$second" | grep -q '"receipt_id"'

receipts="$(curl -fsS "$BASE_URL/v1/management/webhooks/receipts?limit=100" -H "x-wwcx-management-token: $READ_TOKEN")"
printf '%s\n' "$receipts" | grep -q '"durable":true'
printf '%s\n' "$receipts" | grep -q '"provider_event_id":"smoke-webhook-receipt-1"'
printf '%s\n' "$receipts" | grep -q '"processing_status":"accepted"'
printf '%s\n' "$receipts" | grep -q '"processing_status":"duplicate"'
printf '%s\n' "$receipts" | grep -q '"raw_body_retained":false'
printf '%s\n' "$receipts" | grep -q '"unverified_requests_persisted":false'

printf 'WW.CX durable webhook receipt smoke test passed\n'
