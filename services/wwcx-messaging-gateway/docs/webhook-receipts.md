# Durable provider webhook receipts

Phase 3 records each verified and successfully normalized provider webhook attempt before message persistence. PostgreSQL receipts also retain the normalized payload needed for bounded recovery if synchronous message persistence fails.

## Receipt contract

For each verified callback attempt the gateway records:

- receipt UUID;
- selected provider adapter name;
- provider event identifier;
- normalized event UUID for that attempt;
- SHA-256 digest of the exact raw request body;
- normalized payload for recovery;
- verification state;
- processing state (`verified`, `processing`, `accepted`, `duplicate`, or `failed`);
- retry attempt count and bounded error summary;
- receipt, availability, locking, and processing timestamps.

The raw webhook body is not copied into the receipt ledger. The normalized payload is the same bounded message model intended for the message/event store.

## Ordering and failure semantics

The receipt is inserted after provider verification/normalization and before message-store processing. This ordering is deliberate:

- a storage/application failure after verification leaves a durable `verified` receipt with enough normalized data to retry message persistence;
- successful new provider events transition the receipt to `accepted`;
- replayed provider events transition the receipt to `duplicate` while the existing `(provider, provider_event_id)` idempotency key prevents a second message insert;
- recovery claims use PostgreSQL `FOR UPDATE SKIP LOCKED`, so concurrent workers cannot process the same ready receipt;
- database-processing retries are safe because message persistence is transactional/idempotent and does not cross a carrier/network side-effect boundary;
- exhausted recovery attempts become `failed` for operator reconciliation rather than looping forever.

The receipt row is an attempt record, not proof that its normalized event UUID became the canonical persisted message. `provider + provider_event_id` remains the authoritative idempotency identity.

## Bounded recovery worker

`python -m app.inbound_worker --once` processes at most one ready verified PostgreSQL receipt. It requires `WWCX_INBOUND_WORKER_ENABLED=true`; the committed default is `false`. Continuous mode is intentionally absent.

Relevant settings:

- `WWCX_INBOUND_WORKER_ENABLED=false`
- `WWCX_INBOUND_RETRY_DELAY_SECONDS=30`
- `WWCX_INBOUND_MAX_ATTEMPTS=5`

These are application/database recovery controls only. They do not authorize outbound sending or any carrier action.

## Authentication and replay boundary

Only callbacks that pass the selected provider adapter's verification method are persisted. Invalid/unverified requests are deliberately not stored so a future public endpoint cannot become an unauthenticated database-write amplification path.

Real provider adapters must implement provider-specific signature authentication and timestamp/freshness/replay-window rules before returning verified. The simulator token is a development reference only and is not a production signature scheme.

## Read-only observability

`GET /v1/management/webhooks/receipts` is management-token protected and returns bounded counts/recent receipt metadata. It does not expose raw callback bodies, normalized message bodies, media URLs, provider secrets, or mutation authority.

## Remaining carrier-neutral work

This durable inbound recovery path does not activate a provider and does not implement carrier-specific delivery callbacks. Before carrier activation, add and validate each selected provider's cryptographic verification/freshness rules and the provider-neutral delivery/status reconciliation model.
