# WW.CX Outbound Mail Preparation Adapter — 2026-08-01

## Purpose

`tools/outbound_mail_prepare.py` provides a stable no-send integration point for the WW.CX admin console, authenticated operator workflows, approved applications, and future ChatGPT-assisted correspondence workflows.

It accepts structured JSON, applies the canonical outbound-mail policy, appends the controlled signature and records footer, creates an opaque action URL, emits control headers, and produces a metadata-only audit event.

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

The audit record excludes the complete message body and raw action token. It includes hashes, control references, message classification, sender identity, recipient count, and the `prepared_not_sent` delivery state.

## Sender controls

The requested `from_address` must belong to a domain allowed by the canonical policy. The validated sender address is also used in the visible footer and audit identity so the envelope, message body, and evidence do not disagree.

The initial committed allow-list is:

- `ww.cx`
- `creekco.ca`

Changes to sender domains require policy review. Domain inclusion does not prove SPF, DKIM, DMARC, mailbox, or provider readiness.

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
- allowed sender-domain enforcement;
- sender/footer/audit alignment;
- controlled footer and headers;
- no raw action-token or message-body copy in the JSONL audit event;
- optional body and audit outputs;
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
