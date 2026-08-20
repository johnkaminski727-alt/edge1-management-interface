# Mail Room verified state — 2026-08-20

## Authoritative checkpoint

Repository: `johnkaminski727-alt/edge1-management-interface`

Use `main` at or after `942ab5b957ad89075ef27ff977b3c39e3ee8dca9` (PR #490) for the state described here.

This file supersedes the 20260818 Mail Room state and the earlier version of this 20260820 file. Historical files remain useful evidence but are not current resume points.

## Current interpretation

The WW.CX Mail Room is no longer missing a local correspondence path or a provider-native source implementation.

Verified layers now are:

1. **Local Mail Room runtime** — live-accepted on Edge1 on 2026-08-19.
2. **Current Edge1 service/listener presence** — re-verified read-only on 2026-08-20.
3. **Namecheap provider inventory** — physical mailboxes and Catch-All reconciled read-only from provider support evidence.
4. **Namecheap provider-native IMAP source** — implemented, tested, merged, but deliberately unactivated.
5. **Current public DNS provider** — fresh Cloudflare + Google resolver consensus on 2026-08-20 still points `ww.cx` MX to Namecheap Private Email.

Production mail sending, live provider login/ingestion, automatic replies, DNS changes, and provider mutation remain separately gated.

## Live Edge1 evidence

### 2026-08-19 accepted local-functional Mail Room

`docs/communications/unified-communications-live-acceptance-20260819.md` records a successful live acceptance on Edge1:

- `wwcx-outbound-mail-gateway.service` running as `wwcx-mail-gateway:wwcx-mail-gateway`;
- loopback listener `127.0.0.1:8104`;
- runtime entry point `server/outbound_mail_gateway_runtime_server.py`;
- `/var/lib/wwcx-mail-room` mode `0700`;
- `/var/lib/wwcx-mail-room/correspondence.sqlite3` mode `0600`, owned by `wwcx-mail-gateway`;
- two authoritative `local_native` RFC822 fixtures persisted into one explicit thread;
- dedicated `wwcx-private-ai` correspondence status returned `ready_local_native`;
- message and thread reads passed;
- prompt-like content remained untrusted;
- nonce replay failed closed;
- BigBird Mail status/read/thread/prepared-draft integration passed;
- drafts remained `prepared_not_sent`;
- provider selected `none`, `production_provider_ready=false`, external delivery false, send endpoint disabled.

This disproves the earlier assumption that the correspondence store was merely theoretical or necessarily empty.

### 2026-08-20 fresh bounded checks

A Gus/ChatGPT session with the Edge1 Operator connector subsequently verified:

- `edge1.messaging_status` -> `status=ok`;
- `wwcx-outbound-mail-gateway.service` -> loaded, active, running;
- `postfix@-.service` -> active, running;
- `wwcx-messaging-gateway.service` -> active, running;
- `127.0.0.1:8104` remains a loopback-only listener;
- BigBird remains healthy and advertises the bounded Mail tools `mail.status.read`, `mail.correspondence.read`, and `mail.draft.prepare`.

The bounded Operator surface does **not** expose arbitrary live systemd environment/drop-in contents or correspondence-database contents, so it has not independently re-read the current value of `WWCX_MAIL_CORRESPONDENCE_READ_ENABLED` or counted the current DB rows. Do not infer those details from service health alone. The strongest host evidence remains the 2026-08-19 accepted `ready_local_native` result plus the 2026-08-20 active service/listener state.

## Runtime-path clarification

The committed base unit `deploy/messaging/wwcx-outbound-mail-gateway.service` describes the disabled foundation and starts `outbound_mail_gateway_server.py`.

The accepted live runtime used `outbound_mail_gateway_runtime_server.py`. This is not an unexplained mismatch: the repository contains `deploy/messaging/install-outbound-mail-disabled-runtime-migration.sh`, which installs a reversible systemd drop-in overriding the runtime entry point while preserving the fail-closed provider/delivery state.

Do not replace that migration/drop-in model casually.

## Provider-native Namecheap source — merged but not activated

### PR #488 — initial read-only source

Merged as `5783f9d4c3a48e62af8a766bb8bac2c99dbedc0a`.

Added:

- `server/mail_namecheap_imap_source.py`;
- `tests/test_mail_namecheap_imap_source.py`;
- `.github/workflows/mail-namecheap-imap-source.yml`;
- `docs/messaging/namecheap-private-email-imap-source-20260820.md`.

The source:

- hard-pins `mail.privateemail.com:993`;
- uses verified TLS;
- requires a full mailbox address as username;
- accepts a credential only through runtime injection and does not persist/return it;
- selects only `INBOX` read-only;
- uses `UID SEARCH` and `UID FETCH ... (BODY.PEEK[])`;
- implements no STORE/MOVE/COPY/DELETE/EXPUNGE/APPEND/SMTP operation;
- reuses the existing strict RFC822 normalizer;
- persists accepted records as source `namecheap-private-email-imap`, scope `production_native`, authoritative `true`;
- preserves `content_is_untrusted=true`, `send_authorized=false`, `mutation_authorized=false`;
- is not registered, scheduled, deployed, or live-enabled merely because the source exists.

### PR #489 — fail-closed per-message hardening

Merged as `9a0f1d51e3bd458c6ca1a6bee80d78f4f047de67`.

Hardening includes:

- numeric UID ordering before bounded tail selection;
- malformed/unsupported provider messages held out and reported by UID;
- safe neighboring messages continue rather than the entire inbox pass aborting;
- strict parsing is not weakened;
- `failed_count` and `complete` make partial ingestion explicit;
- source/session failures still abort the pass.

Exact-head provider-source tests passed, including idempotency, read-only command restrictions, bounded UID behavior, HTML-only rejection isolation, missing-Message-ID isolation, invalid configuration, and login failure.

## Verified Namecheap provider state

### Provider-admin inventory — 2026-08-02

Namecheap Private Email support ticket `NC-JDV-2953` established read-only provider-visible facts for `ww.cx`:

- Pro subscription active through 2026-11-14;
- three mailbox slots total;
- active physical mailboxes: `blank@ww.cx`, `domaincontact@ww.cx`;
- no aliases on either physical mailbox;
- one unused mailbox slot;
- Catch-All enabled to `blank@ww.cx`;
- mailbox-level auto-forward/filter rules were not inspectable by support and remain unverified.

Physical provider mailboxes are transport plumbing. They do not replace WW.CX logical identities such as `john-inbox@ww.cx` and `maildesk@ww.cx`.

### Fresh public DNS — 2026-08-20 22:53 UTC

PR #490 triggered the existing read-only `mail-domain-inventory` workflow. Cloudflare and Google resolvers agreed:

- MX: `10 mx1.privateemail.com`, `20 mx2.privateemail.com`;
- SPF: `v=spf1 include:spf.privateemail.com ~all`;
- authoritative nameservers: Dyn (`ns1194`, `ns2150`, `ns3190`, `ns4142.dns.dyn.com`);
- no published DMARC record;
- provider inference: `namecheap_private_email`, confidence `high`.

Google Workspace onboarding mail seen on 2026-08-16 still instructed the administrator to verify the domain before custom-domain Gmail use. No later activation notice was found in the connected Gmail account. The fresh MX evidence therefore establishes that Namecheap Private Email remains the current public inbound provider.

PR #490 merged as `942ab5b957ad89075ef27ff977b3c39e3ee8dca9` and updated `config/messaging/mail-provider-inventory.json` plus its validator. All exact-head Mail Room, DNS, Edge1 Operator, and repository-wide validation passed before merge.

## Identity and Catch-All limitation

Namecheap Catch-All to `blank@ww.cx` can receive otherwise-unprovisioned `@ww.cx` local parts, but an IMAP-fetched RFC822 message does not universally prove the SMTP envelope recipient. `To`/`Cc` may omit Bcc or differ from the original Catch-All local part.

Before provider-native Mail is treated as identity-complete, one separately authorized read-only canary must inspect real Namecheap-delivered headers for reliable original-recipient evidence (`Delivered-To`, `X-Original-To`, or equivalent). If no reliable provider header exists, identity-sensitive automation must fail closed rather than guess.

## Current activation posture

Still deliberately disabled/unproven:

- live IMAP login and provider-native ingestion;
- any scheduled Namecheap mailbox polling service;
- mailbox-level forwarding/filter verification;
- provider mailbox/alias provisioning or changes;
- live external inbound acceptance canary;
- live outbound provider delivery and sender allow-list;
- automatic replies;
- production DNS changes;
- final Mail inbound/outbound scanner-runtime activation;
- quarantine release/deletion authority.

No mailbox credentials have been requested, displayed, stored, or used by PRs #488–#490.

## Smallest next activation step

The provider-native engineering bridge now exists. The next step crosses a protected live-access boundary:

1. choose the physical mailbox for the first canary (likely `blank@ww.cx` because Catch-All currently targets it, but do not assume without an explicit activation decision);
2. identify an approved secret location without exposing the credential;
3. explicitly authorize one bounded **read-only** Namecheap IMAP canary;
4. fetch only a small bounded tail with the merged source;
5. verify TLS, UIDVALIDITY/UID behavior, provider headers/original-recipient evidence, duplicate handling, `production_native` provenance, and Mail Room read behavior;
6. do not send, mark Seen, move, delete, alter provider configuration, or enable automatic replies.

Until that specific live canary is authorized, the correct state is **provider-native source implemented and validated, activation pending**.
