# WW.CX Messaging Gateway

Provider-neutral SMS/MMS gateway staged separately from FreePBX and Asterisk.

## Safety boundary

This initial milestone does not change live trunks, transports, firewall rules, DNS, production certificates, carrier profiles, or telephone-number routing. It provides an internal development service and carrier simulator only.

## Capabilities in this milestone

- Health and readiness endpoints
- Normalized inbound messaging event model
- Idempotent carrier webhook intake
- Shared-secret HMAC verification for the simulator provider
- In-memory development event store
- Outbound request validation and queued-state response
- STOP, START, and HELP keyword classification
- Automated API tests

## Run locally

```bash
cd services/wwcx-messaging-gateway
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
export WWCX_SIMULATOR_SECRET=development-only-secret
uvicorn app.main:app --reload --port 8092
```

Run tests:

```bash
pytest
```

## Simulator webhook

The request body must be signed with HMAC-SHA256 using `WWCX_SIMULATOR_SECRET`. Send the lowercase hexadecimal digest in `X-WWCX-Signature`.

```bash
body='{"event_id":"demo-1","from_number":"+16045550101","to_number":"+16045550102","text":"Hello","media":[]}'
sig=$(printf '%s' "$body" | openssl dgst -sha256 -hmac "$WWCX_SIMULATOR_SECRET" -hex | awk '{print $2}')
curl -i http://127.0.0.1:8092/v1/webhooks/simulator \
  -H 'Content-Type: application/json' \
  -H "X-WWCX-Signature: $sig" \
  --data "$body"
```

## Next controlled milestones

1. Replace the in-memory store with PostgreSQL and an immutable raw-event table.
2. Add a durable queue and worker process.
3. Implement Telnyx and Bandwidth signature adapters behind the provider interface.
4. Add private MMS quarantine storage and malware scanning.
5. Build the FreePBX user/DID adapter without changing voice routing.
6. Expose a public webhook only after reverse-proxy, WAF, TLS, firewall, and rollback review.
