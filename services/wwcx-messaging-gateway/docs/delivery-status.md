# Provider-neutral delivery status

A successful synchronous provider submission is not final delivery. Phase 3 therefore keeps the outbound queue's `sent` state as "provider accepted the send request" and records later provider delivery callbacks separately.

## Callback contract

`POST /v1/webhooks/{provider}/delivery` uses the same provider registry and provider-specific webhook verification boundary as inbound message callbacks. The adapter normalizes a carrier-specific callback into:

- provider;
- provider event identifier;
- provider message identifier returned by the original send;
- final normalized status: `delivered`, `failed`, or `undelivered`;
- provider occurrence timestamp;
- bounded raw provider status label for audit context.

Only the simulator adapter is registered. This route does not authorize or configure a real carrier.

## Idempotency and ordering

Delivery callback identity is `(provider, provider_event_id)`. Exact provider-event replays are ignored idempotently.

Current delivery state is keyed by `(provider, provider_message_id)`. Out-of-order callbacks remain durably recorded, but only the newest event by `(occurred_at, provider_event_id)` becomes current state. A late older failure therefore cannot overwrite a newer delivered state.

When a matching outbound message already has the provider message ID, an applied delivery state updates its message status. If a callback arrives before the synchronous send transaction has stored that provider message ID, the current delivery state remains unmatched instead of being discarded.

## Bounded reconciliation

`python -m app.delivery_worker --once` can reconcile at most one current unmatched delivery state that now has a matching outbound message. It requires `WWCX_DELIVERY_RECONCILE_ENABLED=true`; the committed default is `false`, and continuous mode is intentionally absent.

The reconciliation query selects only states that already have a matching outbound message, preventing an early/unmatched provider callback from starving other recoverable states.

## Uncertain send outcomes

An arbitrary exception at the provider send boundary is not automatically retried. Only `ProviderSafeRetryError`, which explicitly means the adapter can prove the provider did not accept or submit the message, authorizes an automatic retry. Other exceptions leave the job in `processing` with `reconcile_required` so a possibly accepted live message is not duplicated.

The delivery-status ledger is one source of evidence for later reconciliation, but it does not by itself authorize retrying an outcome-uncertain submission.

## Read-only observability

`GET /v1/management/delivery/status` exposes bounded counts and recent normalized delivery-event metadata under the management read token. It exposes no provider credentials, raw callback bodies, media URLs, or mutation authority.

## Carrier implementation gate

Before any real provider can be registered, its adapter must independently implement and test provider-specific callback signature authentication, timestamp freshness/replay-window enforcement, payload normalization, and delivery-state mapping. Carrier credentials, DIDs, public webhook exposure, billing, and live traffic remain separate authorization gates.
