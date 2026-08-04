# Authenticated delivery-status notification normalization

Date: 2026-08-04

## Objective

Convert a restricted, authenticated delivery-status notification into minimized provider-neutral delivery events without retaining raw recipient addresses, diagnostics, message content, or credentials.

Components:

- evidence manifest schema: `schemas/messaging/authenticated-dsn-evidence.schema.json`;
- offline normalizer: `tools/messaging/normalize_authenticated_dsn.py`;
- validator: `tests/validate_authenticated_dsn_normalizer.py`.

The normalizer does not log into a mailbox, poll IMAP or POP, expose a listener, contact a provider, apply events to production state, or send mail.

## Evidence prerequisite

A raw DSN `.eml` must remain in a restricted evidence directory outside every Git working tree. A separate manifest must record:

- authenticated-mailbox DSN source;
- `source_verified=true` from the capture procedure;
- SHA-256 of the authenticated mailbox identity;
- SHA-256 of the raw `.eml`;
- selected provider profile;
- SHA-256 of the provider message ID from gateway/provider audit evidence;
- correspondence control ID;
- explicit restricted-message and no-credential markers.

The normalizer verifies the raw-message SHA-256 before parsing. It cannot create or infer source verification.

## Accepted MIME structure

The raw message must be:

```text
multipart/report; report-type=delivery-status
```

and contain exactly one:

```text
message/delivery-status
```

or internationalized:

```text
message/global-delivery-status
```

part with at least one `Final-Recipient` block.

Human-readable text and returned-message content are ignored. Only the machine-readable delivery-status fields are parsed.

## Classification

Supported recipient outcomes are:

- action `failed` with 5.x enhanced status → `permanent_bounce`;
- action `failed` or `delayed` with 4.x status → `transient_bounce`;
- action `delivered`, `relayed`, or `expanded` with 2.x status → `delivered`.

Unsupported or contradictory action/status combinations fail closed.

Diagnostic output is reduced to one bounded class:

- `mailbox_unavailable`;
- `domain_unavailable`;
- `policy_rejection`;
- `rate_limited`;
- `provider_unavailable`;
- `unknown`;
- `none` for delivered events.

The raw `Diagnostic-Code` is never copied into normalized output.

## Recipient minimization

`Final-Recipient` is normalized to lowercase and immediately reduced to SHA-256. The raw address and domain are not emitted. Each recipient block becomes one deterministic delivery event with an ID derived from:

- raw evidence hash;
- recipient hash;
- action;
- enhanced status;
- recipient-block index.

Reprocessing the same evidence therefore produces the same event IDs and can use the delivery-event foundation's idempotence protection.

## Offline command

```sh
python3 tools/messaging/normalize_authenticated_dsn.py \
  --dsn /restricted/dsn/<timestamp>/message.eml \
  --manifest /restricted/dsn/<timestamp>/manifest.json \
  --output /restricted/dsn/<timestamp>/normalized-events.json \
  --pretty
```

The raw DSN, manifest, and output must remain outside Git. The normalizer refuses in-repository evidence or output paths.

## Applying reviewed events

Normalization does not modify suppression state. After a human or authenticated workflow reviews the minimized events, apply each event with the existing offline event CLI:

```sh
python3 tools/messaging/outbound_mail_delivery_event_cli.py \
  apply /restricted/dsn/<timestamp>/one-event.json \
  --database /var/lib/wwcx-outbound-mail/delivery-state.sqlite3
```

Production application requires the authenticated capture procedure, service-account permissions, evidence retention, and deployment authorization to be in place. Do not use `--allow-synthetic` for real DSN evidence.

## Suppression effect

The delivery-event state model provides:

- permanent bounce → durable recipient suppression;
- transient bounce → retryable failure count without suppression;
- delivered → no suppression and transient count reset only when no durable suppression exists.

A later delivery never clears a permanent-bounce, complaint, or unsubscribe suppression automatically.

## Work still required

This normalizer closes the offline DSN parsing and minimization gap. Production bounce ingestion still requires:

1. an exact provider return-path and authenticated bounce mailbox;
2. a capture process proving which mailbox and account produced the raw `.eml`;
3. safe access through an approved credential path;
4. restricted raw evidence retention;
5. automated or reviewed manifest creation without exposing mailbox credentials;
6. service-account event application;
7. monitoring for parse failures, duplicate evidence, and source-verification failures;
8. pilot validation using the controlled one-message contract.

Complaint ingestion remains provider-specific. A complaint must enter through a separately authenticated provider report or reviewed manual evidence import and must create a durable suppression.

## Preserved boundaries

This package does not access a mailbox, create a bounce address, change a return-path, install credentials, expose an endpoint, modify DNS, apply an event to live state, activate a provider or sender, prepare a production message, or send mail.
