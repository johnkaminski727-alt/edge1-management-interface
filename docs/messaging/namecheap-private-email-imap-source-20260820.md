# Namecheap Private Email IMAP source — 2026-08-20

## Purpose

Bridge the existing `ww.cx` Namecheap Private Email inboxes into the private WW.CX Mail Room correspondence store without changing DNS, sending mail, modifying provider state, or embedding credentials.

This document covers an **unactivated source adapter**. It does not authorize a live IMAP login or production mail-flow change.

## Provider facts

Read-only Namecheap support inventory ticket `NC-JDV-2953`, completed 2026-08-02, established the following provider-visible state for `ww.cx`:

- Private Email Pro subscription active through 2026-11-14;
- three mailbox slots available;
- two active physical mailboxes: `blank@ww.cx` and `domaincontact@ww.cx`;
- no aliases on either physical mailbox;
- Catch-All enabled to `blank@ww.cx`;
- one unused mailbox slot;
- Namecheap reported the mail domain configured correctly for send/receive and the default DKIM selector in use;
- mailbox-level auto-forwarding and filter rules were not visible to Namecheap support and require a separate logged-in webmail review.

No provider configuration was changed while gathering that inventory.

Current Namecheap documentation specifies encrypted Private Email IMAP at:

- host: `mail.privateemail.com`;
- port: `993`;
- security: SSL/TLS;
- username: the full mailbox address.

The source implementation therefore hard-pins that endpoint and does not accept caller-supplied host or port values.

## Physical provider mailboxes versus WW.CX logical identities

`config/messaging/mail-identities.json` defines internal delivery roles such as:

- `john-inbox@ww.cx` — private John delivery target;
- `maildesk@ww.cx` — shared role delivery target.

Those are logical WW.CX routing identities, not proven physical Namecheap mailboxes. The provider inventory instead shows `blank@ww.cx` and `domaincontact@ww.cx` as the two physical mailboxes.

Because Namecheap Catch-All targets `blank@ww.cx`, mail addressed to an otherwise unprovisioned `@ww.cx` local part can still arrive in that physical mailbox. The Mail Room must preserve the message's original recipient evidence and apply WW.CX routing policy after ingestion rather than pretending the physical mailbox name is the public identity.

This source does **not** change, create, rename, or delete any mailbox or alias to make the provider inventory resemble the logical registry.

## Source implementation

`server/mail_namecheap_imap_source.py` is a bounded provider-native source that:

1. requires a full mailbox address as the username;
2. obtains the mailbox password from an injected callable at runtime;
3. creates a verified TLS session to `mail.privateemail.com:993`;
4. selects only `INBOX` and always uses IMAP read-only mode;
5. obtains message UIDs with `UID SEARCH`;
6. fetches a bounded tail using `UID FETCH ... (BODY.PEEK[])` so fetching does not mark messages Seen;
7. reuses the existing strict RFC822 normalization, threading, body-size, address, and Message-ID validation;
8. persists accepted messages with immutable provenance:
   - source `namecheap-private-email-imap`;
   - scope `production_native`;
   - authoritative `true`;
9. skips already-ingested authoritative RFC Message-IDs idempotently;
10. returns no credential material and grants no send or mutation authority.

There is deliberately no provider scheduler, systemd unit, secret file, activation flag, SMTP path, mailbox mutation command, or automatic reply behavior in this change.

## Fail-closed behavior

The source rejects or aborts on:

- malformed mailbox usernames;
- a mailbox other than `INBOX`;
- missing credentials;
- TLS/IMAP connection or authentication failure;
- malformed UID responses;
- provider messages without canonical RFC Message-ID;
- RFC822 content that fails the existing Mail Room parser bounds and text-only persistence contract;
- an output store that is not authoritative `production_native`.

Mailbox-modifying IMAP operations are not implemented. The adapter has no SMTP capability.

## Recipient-preservation limitation

RFC822 `To`, `Cc`, and provider-added delivery headers are message evidence, but they are not universally equivalent to the SMTP envelope recipient. Catch-All and Bcc delivery can therefore create cases where the exact original envelope local-part is not recoverable from the fetched message bytes.

The first live provider canary must inspect representative Namecheap-delivered RFC822 headers before WW.CX claims complete Catch-All original-recipient preservation for provider-native mail. If Namecheap provides a reliable `Delivered-To`, `X-Original-To`, or equivalent header, that evidence can be normalized explicitly. If it does not, ambiguous messages must fail closed for identity-sensitive automation rather than guessing.

## Activation boundary

Still requires separate authorization and an approved secret path:

1. choose which physical mailbox(es) to read (`blank@ww.cx`, `domaincontact@ww.cx`, or both);
2. establish the approved credential location without committing or displaying values;
3. authorize one bounded **read-only** live IMAP canary;
4. verify provider headers, UIDVALIDITY/UID behavior, duplicate handling, and Mail Room provenance using real received messages;
5. separately review Private Email Auto-forward and Filter rules through authenticated webmail if required;
6. only after evidence supports it, design a scheduled ingestion service with checkpointing, monitoring, rollback, and secret isolation.

None of those activation actions are performed by this source-only change.

Production sending, provider mailbox changes, DNS/MX/SPF/DKIM/DMARC changes, automatic replies, quarantine release, and external routing remain outside this scope.
