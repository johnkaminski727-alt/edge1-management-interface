# Mail Room live Namecheap ingestion preparation — 2026-08-21

## Status

The header-only provider-read canary is accepted and merged in PR #504.

User continuation after that checkpoint authorizes the next bounded acceptance: fetch exactly one newest complete RFC822 message from the already selected Namecheap mailbox and persist exactly one validated authoritative `production_native` record into the existing private Edge1 Mail Room store. Persistent polling and sending remain outside scope.

## New engineering hardening

Preparation for the live write found that the provider source still inherited generic RFC822 recipient semantics that prefer visible `To`/`Cc` headers. That is insufficient for Catch-All/Bcc/forward identity attribution even though the live header canary proved Namecheap supplies stronger provider delivery evidence.

PR #505 therefore hardens `server/mail_namecheap_imap_source.py` to:

- require provider original-recipient evidence per selected message;
- prefer `X-Original-To` over `Delivered-To`;
- fail closed if the stronger present header is ambiguous or invalid;
- require the authoritative recipient domain to match the configured mailbox domain;
- bind the persisted recipient to the provider-authoritative address rather than visible `To`/`Cc`;
- report only which accepted header supplied the binding, not its value, in ingestion summary metadata.

Messages without acceptable provider original-recipient evidence are held out with `recipient_evidence_rejected` and are not written.

## One-shot acceptance tool

PR #505 adds:

- `tools/messaging/namecheap_imap_ingestion_acceptance.py`
- `tests/test_namecheap_imap_ingestion_acceptance.py`
- `docs/messaging-operations/namecheap-live-ingestion-acceptance-20260821.md`

The tool is default-audit-only and requires a private short-lived authorization plus `--execute` for live activity. It is restricted to:

- `mail.privateemail.com:993`;
- exact mailbox username SHA-256 binding;
- exact target store path SHA-256 binding;
- INBOX;
- one newest message;
- full-message fetch authorized;
- one `production_native` store write authorized;
- no mailbox mutation;
- no send;
- no provider mutation;
- no persistent polling.

It creates an SQLite online backup before the write, requires the store count to advance by exactly one, verifies immutable Namecheap production provenance plus untrusted/non-authoritative flags, emits sanitized evidence only, and can roll back only the exact newly inserted row if post-write validation fails.

## Live target

`/var/lib/wwcx-mail-room/correspondence.sqlite3`

Do not substitute a temporary CI store and call that live acceptance.

## Current execution-path blocker

The available ChatGPT Edge1 Operator MCP path was re-verified as principal `edge1-operator`, host `edge1.ww.cx`, and read-only. Messaging health is `ok`.

The live repository snapshot exposed through that connector is detached at `d326d4546abefa695a293266342a5c1075f010e2`; the connector cannot fetch, deploy, execute arbitrary commands, inject the mailbox credential, or write the correspondence store.

The current ChatGPT runtime has no `.ssh` directory/identity and no usable `ssh` client configuration for alias `edge1`. GitHub Actions currently has only the two dedicated Namecheap mailbox secrets and no Edge1 SSH/deployment secret.

Therefore the remaining live action must be executed by an authenticated write-capable Edge1 operator path, expected to be Fen's attended path or an equivalent approved operator. Do not claim the production store write has occurred until that run returns sanitized evidence and bounded Mail reads confirm the new record.

## Fen handoff requirements

Fen should:

1. wait for PR #505 to be CI-green and merged;
2. update/verify the intended Edge1 source revision without overwriting unrelated work;
3. execute the documented audit-only preflight;
4. inject the existing `blank@ww.cx` secret through a protected runtime-only mechanism;
5. execute exactly one live acceptance against the canonical store;
6. preserve the private database backup only on Edge1;
7. return sanitized evidence: revision, service state, result contract, before/after record counts, hashed message/thread/UID identifiers, accepted recipient-header name, provenance flags, and final bounded Mail read status;
8. stop without enabling polling, sending, auto-replies, DNS/provider changes, or any other activation.
