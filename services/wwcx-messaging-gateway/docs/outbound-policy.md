# Outbound authorization and rate-policy foundation

Status: provider-neutral repository/runtime safety foundation only. No carrier, sender identity, public webhook, billing, or production message authority is activated by this policy.

## Fail-closed authorization

The one-shot outbound worker now requires all of the existing gates plus an explicit outbound policy:

1. global messaging is not paused;
2. provider is registered and in `WWCX_OUTBOUND_PROVIDER_ALLOWLIST`;
3. `WWCX_OUTBOUND_POLICY_ENABLED=true`;
4. normalized sender is present in `WWCX_OUTBOUND_AUTHORIZED_SENDERS`;
5. every destination begins with a prefix in `WWCX_OUTBOUND_DESTINATION_PREFIX_ALLOWLIST`;
6. recipient count does not exceed `WWCX_OUTBOUND_MAX_RECIPIENTS`;
7. text size does not exceed `WWCX_OUTBOUND_MAX_TEXT_CHARS`;
8. recipients are not suppressed;
9. MMS media is not awaiting/requiring quarantine release;
10. durable hourly/daily message-count capacity can be reserved.

The repository defaults keep policy disabled and both sender/destination allowlists empty. Merely registering a future carrier adapter therefore cannot make it send-capable.

## Durable rate reservation

Migration `0004_outbound_policy.sql` adds `messaging_outbound_send_reservations`.

Before provider submission, the worker serializes rate decisions by provider + sender with a PostgreSQL transaction advisory lock. It checks the preceding hour/day reservations and inserts one reservation for the claimed job before calling the provider.

A reservation is not automatically refunded after an exception, rejection, crash, or uncertain provider outcome. That deliberately consumes capacity rather than allowing retry storms or duplicate-send amplification. Operator/provider reconciliation can later establish a more specific recovery policy once real provider idempotency semantics are known.

## Limits

The configured limits are bounded in code:

- recipients/message: 1..32;
- text characters: 1..10,000;
- hourly messages per provider+sender: 1..100,000;
- daily messages per provider+sender: 1..1,000,000.

These are technical safety limits, not a statement that any particular volume is lawful, contractually allowed, financially acceptable, or appropriate for a carrier account.

## Spend control boundary

No dollar-denominated spend limit is implemented here because there is no selected carrier, rate card, currency, tax model, message-segment pricing model, or approved billing account. Inventing a price would create false assurance. Provider-specific cost reservations should be added only after an authorized carrier/pricing source exists.

## Identity/actor boundary

This foundation authorizes configured **sender identities**, not human/AI actors. The existing simulator queue endpoint is development-only. A future production queue API must attach authenticated actor/provenance and evaluate actor-to-sender authorization before a message can enter the send queue.

## Live Edge1 sequencing

Existing Edge1 installations initialized through migrations 0001-0003 must apply migration 0004 before deploying the worker code. Fresh inspection, backup, migration evidence, service verification, and rollback evidence remain required. No live Edge1 migration or restart is implied by merging this repository change.
