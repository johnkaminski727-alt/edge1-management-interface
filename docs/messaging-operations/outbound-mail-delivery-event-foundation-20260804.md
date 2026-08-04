# Outbound mail delivery-event and suppression foundation

Date: 2026-08-04

## Objective

Provide a provider-neutral, offline foundation for bounce, complaint, unsubscribe, rejection, delivery, and provider-acceptance evidence before any provider webhook, public endpoint, mailbox poller, or production message is authorized.

Components:

- event schema: `schemas/messaging/outbound-mail-delivery-event.schema.json`;
- event and suppression library: `server/outbound_mail_delivery_events.py`;
- offline CLI: `tools/messaging/outbound_mail_delivery_event_cli.py`;
- validation: `tests/validate_outbound_mail_delivery_events.py`.

## Event contract

Every event contains only minimized metadata:

- opaque event ID;
- event type and timestamp;
- provider profile;
- SHA-256 of the provider message ID;
- correspondence control ID;
- SHA-256 of the recipient address;
- SHA-256 of the restricted source evidence;
- source-authentication method and verified status;
- bounded diagnostic class;
- retryable flag;
- explicit false markers for raw recipient, raw payload, and message-content storage.

The event record never contains a recipient address, message body, provider credential, raw DSN, raw complaint payload, or complete message headers.

## Supported event types

- `provider_accepted`;
- `delivered`;
- `transient_bounce`;
- `permanent_bounce`;
- `complaint`;
- `unsubscribe`;
- `provider_rejected`.

The diagnostic and retryable fields must match the event type. Only `transient_bounce` is retryable.

## Verified source boundary

An event cannot be applied unless `source_verified=true`. Supported evidence paths are represented by:

- a verified provider signature;
- an authenticated mailbox DSN;
- a reviewed manual evidence import;
- a synthetic test event.

Synthetic events require the explicit `--allow-synthetic` flag. That flag is for isolated tests only and must never be used with a production database.

No provider-specific verification adapter or network listener is included in this foundation. Those are separate, provider-dependent production integrations.

## Suppression policy

The following events create durable recipient suppression:

- `permanent_bounce`;
- `complaint`;
- `unsubscribe`.

A suppression stores only the recipient SHA-256 and bounded event metadata. It is never cleared automatically by a later delivery or provider-acceptance event.

A transient bounce increments the transient-failure count without suppressing. A later delivery resets transient failures only when no durable suppression is active.

`provider_rejected` does not automatically suppress a recipient because the rejection may reflect provider authentication, account, policy, or service configuration rather than a bad recipient.

This module deliberately provides no suppression-removal operation. Any future removal of a suppression requires separate reviewed evidence, operator authorization, and an auditable workflow.

## Idempotence and conflicts

Applying the same event twice is idempotent and does not increment state twice. Reusing an event ID with different evidence fails closed.

SQLite stores:

- immutable minimized event records;
- current hashed recipient delivery state;
- durable suppression reason;
- first suppression event ID;
- latest event type and timestamp;
- event and transient-failure counts.

The database is mode `0600` where the platform permits changing mode.

## Offline use

Validate a minimized event:

```sh
python3 tools/messaging/outbound_mail_delivery_event_cli.py \
  validate /restricted/delivery-event.json
```

Apply a verified event to an isolated local state store:

```sh
python3 tools/messaging/outbound_mail_delivery_event_cli.py \
  apply /restricted/delivery-event.json \
  --database /restricted/outbound-mail-delivery-state.sqlite3
```

Read one recipient-hash state:

```sh
python3 tools/messaging/outbound_mail_delivery_event_cli.py \
  status <recipient-sha256> \
  --database /restricted/outbound-mail-delivery-state.sqlite3
```

The CLI performs no network access and does not open referenced source evidence.

## Production work still required

Before this foundation can affect live submission:

1. select the provider and determine the available DSN, webhook, mailbox, or API evidence path;
2. define provider-specific authentication and replay protection;
3. define a restricted evidence-retention policy;
4. deploy the state database under a dedicated service account;
5. add a pre-send gateway check that refuses every actively suppressed recipient;
6. add bounded monitoring and incident response;
7. validate permanent bounce, transient bounce, complaint, unsubscribe, duplicate, replay, and forged-event cases;
8. authorize and run only the single-message controlled pilot.

## Preserved boundaries

This foundation does not expose a webhook or listener, poll a mailbox, log into a provider, inspect credentials, store raw provider payloads, remove a suppression, alter the gateway configuration, activate a sender or provider, prepare a message, or send a message.
