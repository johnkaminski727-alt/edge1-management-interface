# Durable provider webhook receipts

Phase 3 records each verified and successfully normalized provider webhook attempt before message persistence.

## Receipt contract

For each verified callback attempt the gateway records:

- receipt UUID;
- selected provider adapter name;
- provider event identifier;
- normalized event UUID for that attempt;
- SHA-256 digest of the exact raw request body;
- verification state;
- processing state (`verified`, `accepted`, or `duplicate`);
- receipt and processing timestamps.

The raw webhook body is not copied into the receipt ledger. Normalized message content continues to use the existing message/event store.

## Ordering and failure semantics

The receipt is inserted after provider verification/normalization and before message-store processing. This ordering is deliberate:

- a storage failure after verification leaves a durable `verified` receipt instead of erasing evidence that the callback arrived;
- successful new provider events transition the receipt to `accepted`;
- replayed provider events transition the new receipt to `duplicate` while the existing `(provider, provider_event_id)` message idempotency key prevents a second message insert;
- a receipt that remains `verified` is an operational reconciliation signal and must not be interpreted as successfully processed.

The receipt row is an attempt record, not proof that its normalized event UUID became the canonical persisted message. `provider + provider_event_id` remains the authoritative idempotency identity.

## Authentication and replay boundary

Only callbacks that pass the selected provider adapter's verification method are persisted in this ledger. Invalid/unverified requests are deliberately not stored here so that a future public endpoint cannot become an unauthenticated database-write amplification path.

Real provider adapters must implement their provider-specific signature authentication and timestamp/freshness/replay-window rules before returning verified. The simulator token is a development reference only and is not a production signature scheme.

## Read-only observability

`GET /v1/management/webhooks/receipts` is management-token protected and returns bounded counts/recent receipt metadata. It does not expose raw callback bodies, media URLs, provider secrets, or mutation authority.

## Remaining carrier-neutral work

This receipt ledger does not activate a provider and does not implement carrier-specific delivery callbacks. Before carrier activation, add and validate each selected provider's cryptographic verification/freshness rules and the provider-neutral delivery/status reconciliation model. If asynchronous receipt processing/recovery is later added, it must claim durable work concurrency-safely and preserve the existing idempotency key.
