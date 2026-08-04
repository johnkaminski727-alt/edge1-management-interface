# Controlled outbound-mail pilot evidence contract

Date: 2026-08-04

## Purpose

Define the only evidence record that may be used to judge one future outbound-mail pilot. The contract does not authorize a pilot, enable a provider or sender, install a credential, or send a message. It makes the future acceptance criteria precise and machine-verifiable before any production action is requested.

Files:

- schema: `schemas/messaging/outbound-mail-pilot-evidence.schema.json`;
- offline validator: `tools/messaging/validate_outbound_mail_pilot_evidence.py`;
- safe unexecuted template: `examples/messaging/outbound-mail-pilot-evidence.not-executed.example.json`.

Validate the committed unexecuted template:

```sh
python3 tools/messaging/validate_outbound_mail_pilot_evidence.py \
  examples/messaging/outbound-mail-pilot-evidence.not-executed.example.json \
  --require-not-executed \
  --pretty
```

## Exact pilot scope

An accepted executed pilot is restricted to:

- one provider profile: `smtp_submission`;
- one reviewed provider family;
- one canonical sender verified as a provider object;
- one recipient controlled by WW.CX;
- one `test_business_correspondence` message;
- one subject hash and one body hash;
- no bulk, commercial, customer, regulatory, or emergency traffic.

The recipient address and message content are not stored inline. The record stores cryptographic hashes and restricted evidence-file references.

## Authorization gates

An `executed_pass`, `executed_fail`, or `rolled_back` record cannot substitute for approval. It must reference prior explicit authorization covering:

1. provider terms review;
2. provider credential installation;
3. one sender activation;
4. the runtime cutover;
5. the exact owned recipient;
6. the exact message;
7. production message traffic for that one pilot.

The validator cannot create or infer authorization. The committed template keeps every flag false and has `execution_status=not_executed`.

## Preflight gates

A passing pilot requires all of the following before submission:

- exact clean `main` commit;
- gateway, deployment, external-delivery, send-endpoint, policy, and SMTP-cutover gates enabled through the approved runtime overlay;
- selected and ready provider;
- one allowlisted sender;
- canonical sender provider object verified;
- SPF path verified;
- DKIM DNS record verified;
- DMARC record published;
- aligned return-path defined;
- bounce ingestion ready;
- complaint and suppression handling ready;
- rollback verified.

A false preflight gate makes `executed_pass` invalid.

## Submission and receipt evidence

An accepted pass requires:

- provider acceptance;
- gateway HTTP 200 or 202;
- hashed provider message ID;
- receipt by the exact hashed owned recipient;
- matching subject and body hashes;
- controlled footer and control headers;
- hashed complete received-header evidence;
- matching provider, receipt, recipient, gateway event, and audit identifiers.

The complete headers remain in a restricted evidence file; they are not embedded in the normalized record.

## Authentication acceptance

A passing record requires:

- DKIM result `pass`;
- selector `default`;
- signing domain equal to the visible sender domain;
- DKIM From alignment;
- SPF result `pass`;
- SPF From alignment;
- DMARC result `pass`;
- an observed DMARC policy;
- DMARC alignment.

The current system cannot satisfy this contract because WW.CX has no accepted DMARC record and no controlled sent-message header evidence. Public DKIM DNS presence alone is insufficient.

## Rollback handling

A rollback plan must already exist for an executed pass. A failed pilot must preserve failure reasons. A `rolled_back` record additionally requires:

- rollback execution;
- proof that the system returned to `safe_disabled`;
- a rollback evidence SHA-256 digest.

Validation of a historical pass or rollback never authorizes another message.

## Data minimization and secret handling

The validator recursively rejects inline fields for:

- passwords, secrets, tokens, API keys, authorization headers, cookies, and private keys;
- raw or complete headers;
- raw message bodies;
- recipient addresses.

It accepts only hashes and restricted filesystem references. Evidence-file metadata must explicitly state `contains_credentials=false`.

The validator does not open referenced evidence files, inspect credentials, inspect message content, contact a provider, query DNS, or send mail.

## Current safe state

The committed example validates only as:

```text
execution_status=not_executed
message_count=0
recipient_count=0
message_sent=false
provider_credentials_inspected=false
message_content_inspected=false
```

No production pilot is currently authorized by this contract or repository state.
