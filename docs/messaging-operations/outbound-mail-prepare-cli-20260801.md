# WW.CX Outbound Mail Preparation Adapter — 2026-08-01

## Purpose

`tools/outbound_mail_prepare.py` provides a stable no-send integration point for the WW.CX admin console, authenticated operator workflows, approved applications, and future ChatGPT-assisted correspondence workflows.

It accepts structured JSON, applies the canonical outbound-mail policy and identity registry, appends the controlled signature and records footer, creates an opaque action URL, emits control headers, and produces a metadata-only audit event.

It does **not** connect to SMTP, Gmail, Microsoft Graph, a webhook, or any other external delivery provider.

## Basic use

```bash
python3 tools/outbound_mail_prepare.py \
  --input examples/outbound-mail/prepare-request.json \
  --pretty \
  --output /tmp/prepared-correspondence.json \
  --body-output /tmp/prepared-correspondence.txt
```

The JSON artifact contains:

- `status: prepared_not_sent`;
- `network_activity: false`;
- `external_delivery_attempted: false`;
- normalized request metadata without the original body copy;
- the canonical `sender_selection` result;
- the control ID;
- visible action URL;
- action-token SHA-256;
- control headers;
- the copy-ready message body;
- a metadata-only audit record.

The raw action token is not returned as a separate field and is not written to the audit event. It is necessarily present inside the visible action URL that is inserted into the message.

## Standard input

```bash
cat request.json | python3 tools/outbound_mail_prepare.py --pretty
```

## Example request

```bash
python3 tools/outbound_mail_prepare.py --example --pretty
```

The machine-readable request contract is:

```text
schemas/outbound-mail-prepare-request.schema.json
```

## Optional audit record

```bash
python3 tools/outbound_mail_prepare.py \
  --input request.json \
  --audit-jsonl /var/lib/wwcx-outbound-mail/preparation-audit.jsonl \
  --output prepared.json
```

The audit record excludes the complete message body and raw action token. It includes hashes, control references, message classification, resolved sender identity, selection reason, recipient count, and the `prepared_not_sent` delivery state.

## Canonical sender selection

The adapter loads `config/messaging/mail-identities.json` and uses the same automatic sender-selection rules as the gateway service. Selection precedence is:

1. `system_generated: true` selects the reserved `noreply@ww.cx` identity;
2. `original_recipient` selects the matching managed address for a reply;
3. `identity_hint` selects a canonical sender-profile key or registered sender address;
4. otherwise the registry default `john@ww.cx` is used.

A submitted `from_address` is metadata only and cannot override the registry. The result records whether it was present and whether it was replaced. Manual hints cannot select `noreply@ww.cx`; that identity requires `system_generated: true`.

The resolved sender is used consistently in the normalized request, visible footer, audit record, and eventual email envelope. The artifact includes the selected address, identity key, reason, replacement status, reply-to value, and live-delivery status.

## Managed preparation domains

The preparation policy recognizes these managed domains:

- `ww.cx`
- `creekco.ca`
- `spiritcreekgardens.com`
- `scgardens.ca`
- `omegafx.com`

A domain being recognized for preparation does not prove mailbox existence, SPF, DKIM, DMARC, provider readiness, or authorization to send. The canonical identity registry remains the source of truth for which addresses may be selected.

All sender profiles, the live-sender allow-list, and the global outbound activation flag remain disabled in the committed configuration. This feature chooses a preparation identity; it does not authorize or attempt delivery.

## Commercial messages

Requests classified as `commercial` require an HTTPS unsubscribe URL. The adapter rejects the request otherwise.

## Future ChatGPT integration

A future approved connector can invoke this adapter or the equivalent loopback preparation API with the exact JSON request. The returned copy-ready body can then be reviewed, registered, and submitted through an approved provider adapter.

This separates four stages:

1. draft content;
2. prepare and register under WW.CX policy;
3. operator or workflow approval;
4. provider submission.

Stages 3 and 4 remain distinct. Preparing a message never authorizes or performs delivery.

## Validation

The repository validation automatically runs:

```bash
python3 tests/validate_outbound_mail_prepare_cli.py
```

The validator confirms:

- example generation;
- canonical sender selection by profile, original recipient, and system flag;
- submitted-From replacement;
- request, footer, audit, and envelope identity alignment;
- controlled footer and headers;
- no raw action-token or message-body copy in the JSONL audit event;
- optional body and audit outputs;
- rejection of unknown identities and original recipients;
- commercial unsubscribe enforcement;
- absence of network and SMTP client code in the CLI.

## Deferred production work

The following remain outside this adapter and require separate authorization and validation:

- provider credentials;
- SMTP or API submission;
- DNS authentication changes;
- public action-link endpoint activation;
- bounce and complaint ingestion;
- automatic delivery from ChatGPT;
- production traffic cutover.
