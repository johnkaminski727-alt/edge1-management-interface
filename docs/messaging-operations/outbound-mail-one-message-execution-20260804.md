# One-message outbound-mail execution wrapper

Date: 2026-08-04

## Purpose

`tools/messaging/execute_outbound_mail_one_message_pilot.py` is the final bounded operator wrapper for one future outbound-mail pilot. It is **audit-only by default**. Source merge does not authorize or execute the pilot.

The wrapper consumes:

- the safe-disabled runtime gateway, policy, and identity documents under `/etc/wwcx`;
- the private controlled-activation authorization record;
- the private activation/rollback bundle generated from those exact runtime documents;
- one private request file whose complete canonical SHA-256 is authorized;
- the private hashed-recipient suppression database;
- an exact clean `main` commit.

## Default audit action

The default action performs no runtime replacement, service restart, provider request, or message send. It validates:

- repository state and expected commit;
- runtime document schemas and safe-disabled state;
- authorization issuance, expiry, actor/reference, readiness, and exact hashes;
- activation manifest fields and every generated file hash;
- recomputed expected activated and rollback documents;
- one request, one recipient, one sender hint, one message class, and explicit confirmation;
- signer name/title and the approved runtime-policy mailing address;
- request and recipient hashes;
- absence of an active permanent-bounce, complaint, or unsubscribe suppression.

Audit inputs are read-only. Runtime, authorization, request, bundle, and suppression paths may not contain symlinks. Private files must be mode `0600` or stricter.

## Execute action gates

Execution additionally requires all of the following:

```text
root user
host=edge1.ww.cx
branch=main
working_tree=clean
HEAD=<exact approved 40-character commit>
WWCX_ONE_MESSAGE_PILOT_AUTHORIZED=yes
runtime_root=/etc/wwcx
suppression_database=/var/lib/wwcx-outbound-mail/delivery-state.sqlite3
service=wwcx-outbound-mail-gateway.service
gateway_url=http://127.0.0.1:8104
```

The bundle, authorization, request, runtime files, suppression state, and evidence parent must be root-owned and private as applicable. The evidence directory must not already exist.

## Request contract

The request file is a private JSON object with exactly:

```text
to                   one-item array
subject              non-empty text
body                 non-empty text
message_class        business_correspondence
identity_hint        exact authorized sender address
signer_name          non-empty text
signer_title         non-empty text
mailing_address      exact approved runtime-policy address
confirm_send         true
```

The canonical request SHA-256 and normalized recipient-address SHA-256 must match the authorization and bundle manifest. No CC, BCC, second recipient, attachment, commercial class, regulatory class, or emergency class is permitted.

## Execution transaction

After every preflight passes:

1. Create a new mode-`0700` evidence directory.
2. Copy all three current runtime documents into a mode-`0700` backup directory with mode-`0600` files.
3. Replace the runtime documents with the exact recomputed activated documents.
4. Validate the installed activated documents byte-for-byte semantically.
5. Restart the exact gateway service.
6. Require loopback health and status showing external delivery enabled with exactly one live sender.
7. Make exactly one `POST /outbound-mail/send` request.
8. Never retry the send, regardless of timeout, HTTP response, or provider result.
9. Hash the provider message ID, complete response, and audit event without retaining raw values.
10. Enter rollback immediately.
11. Restore the independent preflight backups.
12. Restart the service.
13. Validate the safe-disabled runtime schemas, exact preflight hashes, health, external delivery disabled, and zero live senders.
14. Write minimized execution evidence.

Any activation, health, status, submission, provider, evidence, or rollback failure is terminal. A failed rollback is surfaced as the highest-severity result.

## Evidence

`execution.json` follows:

```text
schemas/messaging/outbound-mail-one-message-execution.schema.json
```

It stores only:

- repository, authorization, bundle, recipient, payload, and SMTP-canary hashes;
- whether activation and one send attempt occurred;
- bounded HTTP/provider acceptance metadata;
- hashes of provider message ID, response, and audit event;
- rollback and post-rollback state;
- privacy/safety booleans.

It never stores the recipient address, message body, raw provider response, provider credentials, raw provider message ID, or raw gateway audit event. Independent runtime backups are preserved for evidence and emergency operator recovery.

## Operator command shape

Audit example:

```sh
python3 tools/messaging/execute_outbound_mail_one_message_pilot.py \
  --action audit \
  --bundle-dir /restricted/outbound-mail/pilot/activation-bundle \
  --authorization /restricted/outbound-mail/pilot/activation-authorization.json \
  --request /restricted/outbound-mail/pilot/request.json \
  --evidence-dir /var/lib/wwcx-deployment-evidence/outbound-mail/pilot-001 \
  --expected-commit <approved-main-commit>
```

Execute shape, only after separate explicit authorization:

```sh
sudo env WWCX_ONE_MESSAGE_PILOT_AUTHORIZED=yes \
  python3 tools/messaging/execute_outbound_mail_one_message_pilot.py \
  --action execute \
  --bundle-dir /restricted/outbound-mail/pilot/activation-bundle \
  --authorization /restricted/outbound-mail/pilot/activation-authorization.json \
  --request /restricted/outbound-mail/pilot/request.json \
  --evidence-dir /var/lib/wwcx-deployment-evidence/outbound-mail/pilot-001 \
  --expected-commit <approved-main-commit>
```

Do not run the execute action until the user explicitly authorizes the exact provider, credential use, sender, recipient, payload, production message traffic, and runtime cutover.

## Current status

The wrapper is source-only and validated with a fake runtime adapter. CI never invokes systemd, a provider, a credential, DNS, or a live send endpoint.

Live blockers remain:

- execute and accept the safe-disabled runtime migration;
- configure and approve the runtime mailing address;
- install provider credentials through an approved path;
- execute and accept the SMTP authentication-only canary;
- verify the canonical sender provider object and capability;
- prove aggregate-report mailbox, bounce, complaint, and suppression operations;
- explicitly authorize and publish monitoring-only DMARC;
- choose and explicitly authorize one owned recipient and one exact payload;
- explicitly authorize production message traffic and the runtime cutover.
