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

changed='{"event_id":"'"$EVENT_ID"'","provider":"simulator","provider_event_id":"smoke-webhook-receipt-1","direction":"inbound","channel":"sms","from":"+16045550110","to":["+16045550101"],"text":"changed payload under reused event id","media":[]}'
collision_code="$(curl -sS -o /tmp/wwcx-webhook-collision.json -w '%{http_code}' -X POST "$BASE_URL/v1/webhooks/simulator" -H "content-type: application/json" -H "x-wwcx-signature: $TOKEN" -d "$changed")"
test "$collision_code" = "409"
grep -q 'does not match' /tmp/wwcx-webhook-collision.json

bad_code="$(curl -sS -o /tmp/wwcx-webhook-bad-signature.json -w '%{http_code}' -X POST "$BASE_URL/v1/webhooks/simulator" -H "content-type: application/json" -H 'x-wwcx-signature: wrong' -d "$payload")"
test "$bad_code" = "401"
unknown_code="$(curl -sS -o /tmp/wwcx-webhook-unknown.json -w '%{http_code}' -X POST "$BASE_URL/v1/webhooks/not-a-provider" -H "content-type: application/json" -d '{}')"
test "$unknown_code" = "404"

receipts="$(curl -fsS "$BASE_URL/v1/management/webhooks/receipts?limit=100" -H "x-wwcx-management-token: $READ_TOKEN")"
printf '%s\n' "$receipts" | grep -q '"durable":true'
printf '%s\n' "$receipts" | grep -q '"recoverable":true'
printf '%s\n' "$receipts" | grep -q '"provider_event_id":"smoke-webhook-receipt-1"'
printf '%s\n' "$receipts" | grep -q '"processing_status":"accepted"'
printf '%s\n' "$receipts" | grep -q '"processing_status":"duplicate"'
printf '%s\n' "$receipts" | grep -q '"raw_body_retained":false'
printf '%s\n' "$receipts" | grep -q '"unverified_request_rows_persisted":false'

audit="$(curl -fsS "$BASE_URL/v1/management/webhooks/audit" -H "x-wwcx-management-token: $READ_TOKEN")"
printf '%s\n' "$audit" | grep -q '"durable":true'
printf '%s\n' "$audit" | grep -q '"storage_model":"bounded_aggregate_counters"'
printf '%s\n' "$audit" | grep -q '"outcome":"payload_conflict"'
printf '%s\n' "$audit" | grep -q '"outcome":"verification_failed"'
printf '%s\n' "$audit" | grep -q '"provider_bucket":"__unknown__"'

# Stage one verified normalized receipt without inserting it into the message
# store, then prove the bounded recovery worker can claim and persist it.
docker compose -f compose.test.yaml exec -T gateway python -c 'import os; from app.models import NormalizedMessage; from app.webhook_receipts import PostgresWebhookReceiptLedger; m=NormalizedMessage.model_validate({"event_id":"dddddddd-dddd-dddd-dddd-dddddddddddd","provider":"simulator","provider_event_id":"smoke-webhook-recovery-1","direction":"inbound","channel":"sms","from":"+16045550111","to":["+16045550101"],"text":"recoverable receipt","media":[]}); PostgresWebhookReceiptLedger(os.environ["DATABASE_URL"]).record_verified("simulator", m, b"synthetic verified recovery fixture")'

worker="$(docker compose -f compose.test.yaml exec -T -e WWCX_INBOUND_WORKER_ENABLED=true gateway python -m app.inbound_worker --once)"
printf '%s\n' "$worker" | grep -q '"status": "accepted"'

receipts="$(curl -fsS "$BASE_URL/v1/management/webhooks/receipts?limit=100" -H "x-wwcx-management-token: $READ_TOKEN")"
printf '%s\n' "$receipts" | grep -q '"provider_event_id":"smoke-webhook-recovery-1"'
printf '%s\n' "$receipts" | grep -q '"processing_status":"accepted"'

printf 'WW.CX durable webhook receipt, collision, audit, and recovery smoke test passed\n'
