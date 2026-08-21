# Mail Room provider-read canary checkpoint — 2026-08-20

## Status

This checkpoint supersedes any earlier wording that describes provider-native Mail as missing engineering.

As of merge commit `8c184bef8f0664075ff3eb402b8e0d29542b20c2` (PR #492), the WW.CX Mail Room has a source-only, explicitly authorized Namecheap Private Email read canary package in addition to the previously merged provider-native ingestion bridge.

Relevant merged work:

- PR #488 / `5783f9d4c3a48e62af8a766bb8bac2c99dbedc0a`: read-only Namecheap Private Email IMAP -> Mail Room ingestion source.
- PR #489 / `9a0f1d51e3bd458c6ca1a6bee80d78f4f047de67`: numeric UID ordering and per-message fail-closed isolation/hardening.
- PR #490 / `942ab5b957ad89075ef27ff977b3c39e3ee8dca9`: provider-admin inventory reconciliation plus fresh resolver-consensus evidence that `ww.cx` still uses Namecheap Private Email MX.
- PR #491 / `00f4a651d0c6a131688e6709434485c1b869a074`: durable Mail Room current-state/backlog/handoff refresh.
- PR #492 / `8c184bef8f0664075ff3eb402b8e0d29542b20c2`: bounded Namecheap IMAP header-only read canary, schema, validator, and runbook.

## Verified provider facts

Provider-admin evidence from 2026-08-02 recorded:

- Namecheap Private Email Pro active through 2026-11-14;
- active physical mailboxes `blank@ww.cx` and `domaincontact@ww.cx`;
- no aliases;
- one unused mailbox slot;
- Catch-All enabled to `blank@ww.cx`;
- mailbox-level forwarding/filter rules remained unverified.

Fresh public DNS evidence captured 2026-08-20 with Cloudflare + Google resolver consensus recorded:

- `ww.cx` MX `10 mx1.privateemail.com` and `20 mx2.privateemail.com`;
- SPF `v=spf1 include:spf.privateemail.com ~all`;
- provider inference `namecheap_private_email` with high confidence;
- no published `ww.cx` DMARC record at that observation.

The August 16 Google Workspace welcome/onboarding message remains setup evidence only; it did not establish a completed MX migration.

## Canary package

Files merged by PR #492:

- `tools/messaging/namecheap_imap_read_canary.py`
- `schemas/messaging/namecheap-imap-read-canary-authorization.schema.json`
- `tests/validate_namecheap_imap_read_canary.py`
- `docs/messaging-operations/namecheap-imap-read-canary-20260820.md`

Safety properties:

- default mode is audit-only;
- audit-only mode performs no network activity and reads no credential;
- live mode requires `--execute`;
- authorization file must be a private regular file outside Git;
- authorization expires within 24 hours and is bound to the fixed Namecheap endpoint plus exact mailbox username SHA-256;
- endpoint is hard-pinned to `mail.privateemail.com:993` using the verified system TLS trust store;
- only `INBOX` may be selected and selection is `readonly=True`;
- at most 5 newest UIDs may be inspected;
- fetch operation is only `BODY.PEEK[HEADER]`;
- no message body, MIME part, or attachment fetch exists in the canary;
- no `STORE`, `MOVE`, `COPY`, `DELETE`, `EXPUNGE`, `APPEND`, Mail Room store write, SMTP, DNS, or provider mutation exists in the canary;
- emitted message/provider identifiers are minimized to SHA-256 hashes and header-presence booleans;
- no credential is accepted on the command line or emitted in evidence.

Exact-head validation for PR #492 passed:

- `Validate repository`: success;
- `Edge1 Operator Validation`: success;
- new `validate_namecheap_imap_read_canary.py`: passed within the repository Python validation phase;
- JSON/shell/JavaScript checks: success;
- Python 3.6 compatibility check: success.

CI used only synthetic IMAP fixtures and did not contact Namecheap.

## Authorized live attempt — 2026-08-21

At 2026-08-21T01:44Z John explicitly authorized the previously defined one-time credential-backed provider-read canary. The authorized mailbox was resolved to the existing Catch-All target `blank@ww.cx`; the live scope remained `mail.privateemail.com:993`, verified TLS, `INBOX` read-only, `max_messages=1`, `BODY.PEEK[HEADER]` only, sanitized evidence, logout and stop.

Gus verified the available Edge1 execution path before attempting provider access:

- `edge1-operator-mcp` identity/health: healthy;
- authenticated principal: `edge1-operator`;
- Operations API health: ok;
- `mutations_enabled=false`;
- Messaging health: ok.

That connector is read-only and cannot consume the mailbox credential or execute the canary. The current ChatGPT runtime also had no SSH identity configured for Edge1.

A one-shot, non-merged GitHub Actions execution branch was therefore created to use repository secrets without exposing them:

- branch: `agent/namecheap-imap-live-canary-20260821`;
- trigger commit: `3d0ee65141e6592a666abe992e7025727099ad6f`;
- workflow run: `32437669015`;
- run guard: only a commit containing `[RUN-NAMECHEAP-IMAP-CANARY-ONCE]` executes the live job;
- mailbox binding: exact SHA-256 for `blank@ww.cx`;
- message bound: one newest header.

The run failed safely in preflight at `Verify secret availability and authorized mailbox binding` because repository Actions secrets `WWCX_NAMECHEAP_IMAP_USERNAME` and `WWCX_NAMECHEAP_IMAP_PASSWORD` were not configured. The authorization-build, IMAP-execution, sanitized-evidence, and artifact-upload steps were all skipped.

**No Namecheap provider socket/session was opened. No mailbox credential was exposed, entered, retrieved, inspected, or used.** This is not an authentication rejection and is not evidence of a provider failure.

## Current authority boundary

The one-time header-only provider canary is authorized, but execution is blocked solely by the absence of an approved secret-backed runtime path containing the existing `blank@ww.cx` mailbox credential.

The exact remaining prerequisite is to make that existing credential available through an approved secret mechanism without placing it in Git, Google Drive, logs, chat, or a command transcript. Acceptable execution paths include a properly protected Edge1 runtime secret/environment or repository Actions secrets dedicated to this bounded canary. Do not reset or rotate the mailbox password merely to satisfy the canary unless separately authorized.

Once an approved secret path exists, the authorized canary remains limited to:

1. `blank@ww.cx` only;
2. `mail.privateemail.com:993`;
3. verified TLS;
4. `INBOX` selected read-only;
5. one newest message header via `BODY.PEEK[HEADER]`;
6. sanitized evidence only;
7. logout and stop.

It must not be combined with provider ingestion, full-message/body reads, Mail Room store writes, mailbox/provider changes, SMTP authentication, outbound mail, DNS changes, sender activation, forwarding/alias changes, auto-replies, password reset/rotation, or any other production activation.

## Subsequent boundary after a successful header canary

A successful header-only provider canary would establish only reachability, authentication, TLS, read-only mailbox selection, and bounded header access.

Full provider-native ingestion through `server/mail_namecheap_imap_source.py` remains a separate later authorization because it fetches complete messages using `BODY.PEEK[]` and writes validated correspondence into the private `production_native` store.

## Resume instruction

Read this checkpoint after `.agent/mail-room-current-state-20260820.md`, `.agent/mail-room-backlog-20260820.md`, and `.agent/mail-room-handoff-20260820.md`.

Do not reopen provider-selection or missing-adapter work unless newer direct evidence shows regression. Provider-read engineering is built and CI-green. The only immediate blocker is approved secret availability for the already-authorized one-time header canary.
