# Namecheap Private Email -> Mail Room one-shot live ingestion acceptance

Date: 2026-08-21

## Objective

Validate exactly one real provider-native inbound message end to end from the existing Namecheap Private Email mailbox into the existing private Edge1 Mail Room correspondence store.

This is an acceptance run, not activation of a polling service.

## Authorized scope

The bounded acceptance may:

- authenticate to the already selected physical mailbox using an approved secret-backed runtime path;
- connect only to `mail.privateemail.com:993` with verified TLS;
- select only `INBOX` read-only;
- inspect the mailbox UID list;
- fetch exactly one newest complete RFC822 message with `BODY.PEEK[]`;
- require reliable provider original-recipient evidence, preferring `X-Original-To` over `Delivered-To`;
- normalize the message under the existing strict Mail Room rules;
- create an SQLite online backup of the existing private correspondence database before mutation;
- persist exactly one new authoritative `production_native` correspondence record;
- validate the before/after record count, provenance, untrusted-content flag, and non-authority flags;
- emit only sanitized evidence containing counts, hashes, booleans, and provider/header metadata.

The acceptance must not:

- mark mail Seen;
- STORE, MOVE, COPY, DELETE, EXPUNGE, or APPEND provider mail;
- send SMTP mail;
- alter Namecheap mailbox/provider settings;
- change DNS/MX/SPF/DKIM/DMARC;
- enable automatic replies;
- enable or install persistent polling;
- emit credentials, message bodies, subjects, addresses, raw Message-IDs, raw UIDs, or raw thread IDs.

## Provider recipient rule

The 2026-08-21 header-only canary proved that a real Namecheap-delivered message exposed both `X-Original-To` and `Delivered-To` header names.

Provider-native ingestion must therefore fail closed per message unless an accepted original-recipient header is present and resolves to exactly one address in the mailbox domain.

Precedence is:

1. `X-Original-To`
2. `Delivered-To`

If `X-Original-To` is present but ambiguous or invalid, do not fall through to `Delivered-To`. Visible `To`/`Cc` headers are not authoritative for Catch-All/Bcc/forward identity attribution.

## Live target

Canonical store:

`/var/lib/wwcx-mail-room/correspondence.sqlite3`

The existing store and parent directory must already be private regular non-symlink paths. The acceptance tool does not create a replacement production database.

## Tool

`tools/messaging/namecheap_imap_ingestion_acceptance.py`

Default mode is audit-only. Live network/store activity requires `--execute` plus a short-lived private authorization file and the runtime variables:

- `WWCX_NAMECHEAP_IMAP_USERNAME`
- `WWCX_NAMECHEAP_IMAP_PASSWORD`

Do not put either value in Git, Drive, issues, PRs, shell history, or evidence.

## Short-lived authorization

Create the authorization file outside the repository, mode `0600`, with a validity window no longer than one hour. The file is bound to:

- the fixed provider host hash;
- port 993;
- the exact mailbox username hash;
- the exact live store path hash;
- `INBOX`;
- `max_messages=1`;
- full-message fetch = authorized;
- `production_native` store write = authorized;
- mailbox mutation = false;
- mail send = false;
- provider mutation = false;
- persistent polling = false.

Generate hashes inside the authenticated runtime. Never paste the credential into the authorization file.

## Recommended Edge1 execution sequence

1. Verify host is exactly `edge1.ww.cx` and identify the authenticated principal.
2. Verify the checked-out repository revision contains this acceptance tool and the original-recipient hardening.
3. Verify `wwcx-outbound-mail-gateway.service` is healthy and `127.0.0.1:8104` remains loopback-only.
4. Verify the database exists, is not a symlink, and has no group/other permission bits.
5. Inject the existing mailbox credential from the approved secret source into the process environment without printing it.
6. Create the private short-lived authorization file under an approved runtime-private directory such as `/run/wwcx-mail-room/`.
7. Run audit-only mode first.
8. Run exactly one live execution as the account that already owns/has intended write access to the Mail Room store.
9. Preserve only the sanitized JSON result and the private SQLite backup. Do not copy either database file into Git or Drive.
10. Verify the resulting provider-native record is visible through the existing bounded Mail correspondence read path and remains `content_is_untrusted=true`, `send_authorized=false`, and `mutation_authorized=false`.
11. Stop. Do not create a timer, daemon, cron entry, or recurring workflow.

Example invocation shape (credential values intentionally omitted):

```sh
python3 tools/messaging/namecheap_imap_ingestion_acceptance.py \
  --authorization /run/wwcx-mail-room/namecheap-ingestion-authorization.json \
  --store /var/lib/wwcx-mail-room/correspondence.sqlite3

python3 tools/messaging/namecheap_imap_ingestion_acceptance.py \
  --authorization /run/wwcx-mail-room/namecheap-ingestion-authorization.json \
  --store /var/lib/wwcx-mail-room/correspondence.sqlite3 \
  --execute \
  --output /var/lib/wwcx-mail-room/acceptance/namecheap-ingestion-result.json
```

## Success criteria

Success requires all of the following:

- provider connection/authentication succeeds;
- INBOX is read-only;
- exactly one UID is selected and fetched with `BODY.PEEK[]`;
- provider original-recipient evidence passes strict binding;
- strict RFC822 normalization succeeds;
- exactly one new store row is created;
- total store record count increases by exactly one;
- persisted provenance is `namecheap-private-email-imap` / `production_native` / authoritative;
- content remains untrusted;
- send/mutation authority remains false;
- sanitized evidence contains no raw correspondence content or credentials.

If the newest message is already ingested, lacks valid original-recipient evidence, lacks a canonical Message-ID, or fails strict normalization, the acceptance is not successful. Do not widen the fetch automatically; stop and evaluate the bounded failure.

## Rollback behavior

An SQLite online backup is created before the attempted store write. If the tool inserts one record and post-write validation then fails, it attempts to remove only that exact newly inserted row after verifying its immutable Namecheap `production_native` provenance. It never restores the entire database automatically, avoiding loss of unrelated concurrent writes.

The private pre-write backup remains available for operator evidence/recovery. It contains correspondence data and must remain in protected Edge1 storage.

## Current execution-path note

The ChatGPT Edge1 Operator connector available during preparation is read-only, and the ChatGPT runtime has no configured Edge1 SSH identity. Therefore this document and tool prepare the live action but do not claim it has run on Edge1. The live step must be performed through an authenticated write-capable Edge1 operator path (for example Fen's attended Edge1 path) without exposing the mailbox secret.
