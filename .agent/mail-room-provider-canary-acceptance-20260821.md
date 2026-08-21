# Mail Room provider-read canary acceptance — 2026-08-21

## Result

The explicitly authorized one-time Namecheap Private Email provider-read canary for the WW.CX Catch-All mailbox completed successfully on 2026-08-21.

This acceptance proves only the bounded provider-read properties listed below. It does **not** authorize ongoing provider polling, full-message ingestion, Mail Room store writes, outbound mail, mailbox mutation, DNS changes, provider configuration changes, aliases/forwarders, or automatic replies.

## Authorized scope

- provider: Namecheap Private Email;
- endpoint: `mail.privateemail.com:993`;
- transport: verified TLS;
- physical mailbox: existing Catch-All target `blank@ww.cx`;
- mailbox: `INBOX` only;
- selection: read-only;
- maximum messages: 1 newest UID;
- fetch: `BODY.PEEK[HEADER]` only;
- no message body, MIME part, or attachment fetch;
- no `STORE`, `MOVE`, `COPY`, `DELETE`, `EXPUNGE`, or `APPEND`;
- no Mail Room store write;
- no SMTP or message send;
- no provider/DNS mutation;
- sanitized evidence only.

## Execution evidence

GitHub Actions repository secrets were created for the dedicated canary variable names. Secret values are not recorded in Git, this document, logs, Google Drive, or any evidence artifact.

First credential-backed retry of workflow run `32437669015`:

- secret availability: PASS;
- exact username SHA-256 binding to the authorized mailbox: PASS;
- short-lived authorization creation: PASS;
- provider read: transient transport failure after approximately 20 seconds;
- no acceptance evidence produced by that attempt.

A diagnostic one-shot branch revision added a credential-free TLS/IMAP greeting preflight while preserving the same live-read scope and removing fallback references to generic SMTP secret names.

Successful run:

- GitHub Actions run: `32439971393`;
- job: `96648529437`;
- source branch commit: `92c4412671c9a1d98797f463bd5cb14ecf77e49d`;
- completed at approximately `2026-08-21T02:28:43Z`;
- sanitized artifact ID: `9432045627`;
- artifact retention: 1 day.

## Accepted checks

The successful run established:

1. DNS resolution for the fixed Namecheap IMAP hostname succeeded.
2. TCP/TLS connection to port 993 succeeded.
3. TLS negotiation succeeded with TLS 1.3 and normal certificate verification.
4. A valid IMAP server greeting was received before authentication.
5. Dedicated repository secrets were present.
6. The hidden username hashed to the exact authorized `blank@ww.cx` username binding.
7. Authentication succeeded.
8. `INBOX` was selected read-only.
9. One newest UID was inspected with `BODY.PEEK[HEADER]` only.
10. Sanitized evidence reported `selected_count=1` and `uidvalidity=1732489496`.
11. The inspected message had a Message-ID.
12. Recipient metadata was present.
13. Provider delivery metadata included both `Delivered-To` and `X-Original-To` header names.
14. No Bcc header was present in the inspected header block.
15. No message body was fetched.
16. No mailbox mutation was authorized or performed.
17. No Mail Room store write was authorized or performed.
18. No mail send was authorized or performed.
19. No credential value was emitted.

Provider/message identifiers in the result remain SHA-256 minimized. Raw message addresses, subject, body, credential, UID, and Message-ID are not recorded here.

## Identity implication

The earlier provider-native identity blocker is materially narrowed: at least one real Namecheap-delivered message exposed both `Delivered-To` and `X-Original-To` header names during the bounded canary.

This proves that the provider can expose original/delivery-recipient metadata on real mail. It does **not** prove that every possible delivery path, Bcc case, alias, forwarder, or malformed message will contain one of those headers. Production ingestion must therefore continue to fail closed when reliable original-recipient evidence is absent or ambiguous.

## Security cleanup

After the successful run, the temporary secret-consuming workflow on branch `agent/namecheap-imap-live-canary-20260821` was disarmed by commit `b13cfb100a3c37d86b2cf373c31a463f0063a571`:

- no repository-secret references remain in the workflow;
- its only job has `if: false`;
- it cannot execute the provider canary.

The repository secrets themselves remain encrypted repository secrets and are not copied into source or evidence.

## Current boundary

The header-only provider canary is **accepted**.

The next provider-native step remains separately gated because `server/mail_namecheap_imap_source.py` fetches complete messages with `BODY.PEEK[]` and can write validated correspondence to the private `production_native` store.

Do not infer authorization for that ongoing/full-message ingestion from this acceptance. A later activation must separately define mailbox scope, polling/execution model, private secret location, full-message/store-write authority, rollback, evidence, failure handling, and whether it is a one-shot ingestion or persistent service.
