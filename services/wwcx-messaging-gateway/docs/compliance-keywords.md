# SMS keyword compliance foundation

Status: provider-neutral repository/runtime foundation only. This does not claim complete legal, regulatory, carrier, CTIA, TCPA, CASL, or other jurisdiction-specific compliance and does not activate production messaging.

## Behavior

For accepted inbound **SMS** messages, the gateway recognizes the existing exact keyword sets:

- STOP actions: `STOP`, `STOPALL`, `UNSUBSCRIBE`, `CANCEL`, `END`, `QUIT`
- START actions: `START`, `UNSTOP`, `YES`
- HELP actions: `HELP`, `INFO`

Matching is case-insensitive after trimming surrounding whitespace. Natural-language messages such as `Please stop by tomorrow` are not treated as commands.

Every recognized command is written to `messaging_compliance_events`. STOP and START also update `messaging_consent_state`. The legacy `suppressions` table remains the outbound enforcement source so the existing worker fails closed for suppressed destinations.

## Ordering and replay safety

Carrier callbacks can arrive late or out of order. STOP/START state therefore uses the message `occurred_at` timestamp, with the event UUID as a deterministic tie-breaker. A command older than the current effective state is audited with `applied=false` and cannot undo a newer decision.

Duplicate provider events remain idempotent through the existing `(provider, provider_event_id)` uniqueness gate and do not create duplicate compliance events.

## Manual suppression preservation

Keyword STOP writes `reason=keyword:stop`. Keyword START removes only suppressions whose reason begins with `keyword:`. A non-keyword/manual suppression is not removed by START, and a later keyword STOP does not overwrite its reason/source metadata.

This separation is intentional: a user-facing keyword state must not silently erase a separate abuse, safety, administrative, or other operator suppression.

## HELP and replies

HELP is audited but does not change suppression state. The gateway does **not** automatically transmit HELP, STOP-confirmation, or START-confirmation replies in this foundation. Auto-replies are outbound production behavior and remain disabled until an approved provider adapter, sender identity, message content, consent policy, spend/rate controls, and explicit production authority exist.

## Management visibility

Authenticated read-only management can inspect `/v1/management/compliance`, which reports:

- total and keyword suppression counts;
- active/suppressed keyword consent-state counts;
- STOP/START/HELP event counts;
- stale-event count;
- bounded recent compliance events and whether each event was applied.

The endpoint explicitly reports `auto_reply_enabled: false`, `regulatory_compliance_claimed: false`, and `mutation_authorized: false`.

## Deployment sequencing

Version 0.4.4 introduces migration `0003_compliance_keywords.sql`. Existing Edge1 PostgreSQL installations already initialized with migrations 0001/0002 must apply 0003 **before** deploying 0.4.4 code. The migration is additive; live application remains a separately verified Edge1 change with backup/rollback evidence.

No carrier credentials, DID, public webhook, DNS, firewall, TLS, billing, contract, or production traffic change is part of this increment.
