# Durable provider webhook receipts

Phase 3 records each verified and successfully normalized provider webhook attempt before message persistence. PostgreSQL receipts retain the normalized payload needed for bounded recovery if synchronous message persistence fails.

## Receipt contract

For each verified callback attempt the gateway records the receipt UUID, selected provider, provider event identifier, normalized event UUID, SHA-256 digest of the exact raw request body, normalized recovery payload, verification/processing state, retry metadata, and timestamps. Raw callback bodies are not retained in the receipt ledger.

## Idempotency and payload collisions

`provider + provider_event_id` is the authoritative message idempotency identity. A replay with the same provider event ID is compared against the first processed webhook receipt's exact raw-body SHA-256 digest:

- identical body: treated as an idempotent duplicate;
- changed body under the same event ID: rejected with HTTP 409 and counted as `payload_conflict`;
- no prior receipt because the event predates the receipt ledger: conservatively treated as an ordinary duplicate because the historical raw-body digest is unavailable.

The comparison deliberately uses the received body digest rather than internally generated fields such as event UUIDs or default timestamps, which can differ between normalizations of the same provider callback.

## Durable recovery

The receipt is inserted after provider verification/normalization and before message-store processing. A storage/application failure therefore leaves a durable `verified` receipt with enough normalized data to retry. Recovery claims use PostgreSQL `FOR UPDATE SKIP LOCKED`; successful new events become `accepted`, genuine replays become `duplicate`, and exhausted database-processing retries become `failed`.

`python -m app.inbound_worker --once` processes at most one ready verified PostgreSQL receipt. It requires `WWCX_INBOUND_WORKER_ENABLED=true`; the committed default is `false`. Continuous mode is intentionally absent.

## Authentication and replay boundary

Provider-specific signature authentication, timestamp freshness, and replay-window enforcement are adapter obligations. The simulator shared token is a development reference only and is not a production security scheme.

Unverified requests are not stored as append-only request rows. Instead, the gateway maintains bounded durable aggregate counters for known-provider verification failures and related boundary outcomes. Unknown provider path values are collapsed into the single `__unknown__` bucket. This preserves durable probing/replay visibility without allowing arbitrary unauthenticated requests to create an unbounded number of database rows.

## Read-only observability

`GET /v1/management/webhooks/receipts` returns bounded verified receipt metadata. `GET /v1/management/webhooks/audit` returns bounded aggregate boundary counters. Both require the management read token and expose no raw callback bodies, media URLs, provider credentials, or mutation authority.

## Carrier boundary

The durable receipt, collision, audit, and recovery paths do not activate a provider. Before any real provider is registered, its adapter must independently implement and test cryptographic verification, timestamp freshness/replay-window rules, payload normalization, and the already-defined provider-neutral delivery-status mapping.
