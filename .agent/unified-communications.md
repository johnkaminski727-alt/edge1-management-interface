# Unified Communications — Current State

Last reconciled: 2026-08-18, Phase 28 closeout
Repository: `johnkaminski727-alt/edge1-management-interface`
Phase 28 implementation PR: #427
Reviewed implementation head: `88253f0c3c2839b2192cc1d9f723c92a79b293be`
Phase 28 implementation merge: `e7d7fda638a4f69d68bf54cdebdbee9070143384`
Global `fresh_edge1_runtime_verified`: **false**

## Current truth

WW.CX Communications remains read-only/non-sending by default. Phase 28 delivered and merged a functional local-native Mail correspondence software path while preserving all production, provider, authentication-policy, and quarantine-release boundaries.

The merged functional chain is:

`local RFC822 file -> bounded local-native parser -> private SQLite message/thread store -> authenticated loopback Mail API -> BigBird Mail facade -> mail.correspondence.read`

No Phase 28 state grants live Mail send, live SMS/MMS, call origination, route/trunk/dialplan mutation, generic execution, provider credentials, quarantine release, or new public management exposure.

## Repository and CI state

Phase 28 began from current `main` `9711461125a73f013b0f0a09347a6b1d1105eb5f`, which already included PR #426's fail-closed durable outbound Messaging queue. Unrelated SNMP and other parallel work was preserved.

PR #427 merged the Phase 28 implementation as `e7d7fda638a4f69d68bf54cdebdbee9070143384` after exact-head validation passed on `88253f0c3c2839b2192cc1d9f723c92a79b293be`:

- Validate repository — run `32196436559` — PASS;
- Edge1 Operator Validation — run `32196436531` — PASS;
- Validate outbound mail suppression server — run `32196436670` — PASS.

No review threads remained before merge.

## Functional local Mail correspondence

### Local native source

`server/mail_local_rfc822_source.py` provides a bounded provider-independent local source:

- local RFC822 bytes/files only;
- no network activity;
- canonical `Message-ID` required;
- timezone-bearing `Date` required;
- explicit `In-Reply-To` / `References` threading only;
- optional native/provider message/thread IDs preserved when supplied;
- bounded `text/plain` body persistence;
- attachment bytes ignored;
- HTML-only input fails closed;
- no subject/name-similarity thread inference;
- persisted source `local-mailroom-rfc822`, scope `local_native`, authoritative `true`;
- local-native truth remains `production_provider_ready=false`.

`tools/mail_local_intake.py` is the operator intake entry point and constrains runtime persistence to the private Mail Room root `/var/lib/wwcx-mail-room`.

### Store and provenance

`server/mail_correspondence_store.py` now persists immutable source, authority, and source scope. Supported scopes are `synthetic`, `local_native`, `production_native`, and fail-safe `legacy_unscoped`.

Only persisted records with `authoritative=true` and scope `local_native` or `production_native` can cross the Private AI correspondence-read boundary. Synthetic records cannot claim authority and cannot be upgraded by reopening the database. Read-only consumers use SQLite `mode=ro` and reject writes.

### Mail AI/API

`server/mail_ai_adapter.py` supports bounded message and thread reads. Correspondence reads remain disabled by default and fail closed unless the private store is valid and contains readable authoritative records.

`server/outbound_mail_gateway_server.py` exposes correspondence status/message/thread reads behind the existing HMAC/replay-protected loopback API. The endpoints additionally require exact client ID `wwcx-private-ai`.

A Phase 28 manual security review found and fixed a potential privilege inheritance issue before merge: the already-authorized `wwcx-website-admin` client could otherwise have inherited message-body read access. `tests/validate_mail_correspondence_client_isolation.py` now proves existing/unrelated HMAC clients are rejected from correspondence endpoints.

The unauthenticated public status surface does not expose correspondence data or the private database path.

### BigBird repository integration

Merged components:

- `integrations/bigbird_mail/client.py`;
- `integrations/bigbird_mail/tools.py`;
- `integrations/bigbird-mail/tool-manifest.json`.

The client is loopback-only and HMAC-authenticated. The facade rechecks untrusted-content, non-mutation, no-send, and persisted provenance boundaries. It exposes repository tools for `mail.status.read`, `mail.correspondence.read`, and `mail.draft.prepare`; it has no send method. Draft preparation remains `prepared_not_sent`.

The base/deployed HMAC allowed-client policy was deliberately left unchanged. The proposed live client `wwcx-private-ai` was registered only inside isolated integration-test configuration. Adding it live is an authentication-policy change requiring separate explicit approval.

## Functional acceptance

The merged exact-head repository validator executed the complete local path using generated fixtures:

- root RFC822 ingest;
- reply RFC822 ingest and explicit thread reconstruction;
- native/provider ID preservation;
- local private permissions in the fixture;
- HTML-only fail-closed behavior;
- synthetic-record isolation;
- arbitrary runtime DB path rejection;
- direct Mail AI reads;
- unsigned API rejection;
- HMAC-authenticated correspondence reads;
- dedicated-client isolation;
- BigBird facade message/thread reads;
- prompt-like body retained as untrusted data;
- prepared-not-sent draft with live delivery authorization false.

This satisfies the provider-independent functional software fallback. It does not imply live Edge1 deployment or provider-production correspondence.

## MMS state

Phase 27's merged repository MMS implementation remains ready for live acceptance:

- private content-addressed quarantine store;
- SHA-256/integrity checks;
- fail-closed quarantine states;
- fixed `/usr/bin/clamscan` adapter;
- local clean/EICAR/error/restart acceptance tooling;
- no automatic quarantine release.

Live Edge1 scanner/private-root acceptance was not executed in Phase 28 because this session exposed no authenticated Edge1 execution connector and no usable local SSH identity. SMS/MMS `security_quarantine` therefore remains `degraded` until actual host evidence exists.

## Existing shared runtime truth

Prior accepted live evidence remains unchanged unless later fresh Edge1 evidence proves otherwise:

- Messaging Gateway/PostgreSQL — runtime-ready from prior acceptance; PR #426's durable outbound queue is merged on main but Phase 28 did not live-operate it;
- BigBird — previously runtime-ready for accepted Messaging/communications/telephony scopes; Phase 28 Mail tools are merged but not live-registered;
- Communications workspace/Relay — previously runtime-ready, loopback-only, authoritative Relay metadata attached;
- Voice/SIP — bounded read-only acceptance remains runtime-ready; current external interconnect health remains `unknown` because the prior degraded display came from a stored 2026-07-20 status snapshot, not a fresh live probe.

## Remaining blockers

1. **Authenticated Edge1 execution path** — required for live MMS scanner/private-root deployment and acceptance, live local-Mail deployment, service/listener/permission/restart checks, and rollback evidence.
2. **Authentication-policy approval** — required before adding `wwcx-private-ai` to the deployed Mail HMAC allowlist and live-registering the BigBird Mail tools. Do not reuse `wwcx-website-admin` to bypass this boundary.
3. **Production-native Mail source** — required only before claiming provider-production correspondence readiness. The local-native software path is already functional without it.

Exact live procedure: `docs/communications/unified-communications-phase28-live-acceptance-20260818.md`.

Durable Phase 28 evidence:

- `.agent/unified-communications-validation-phase28-20260818.md`;
- `docs/communications/unified-communications-phase28-live-acceptance-20260818.md`;
- `docs/handoff/unified-communications-phase28-20260818.md`.

`fresh_edge1_runtime_verified` remains false.

## Production boundaries

Without separate explicit authorization, do not send live SMS/MMS or email, originate production calls, change emergency/SIP/carrier routing, modify DNS/firewall/certificates/authentication policy, rotate/disclose credentials, release quarantine, port numbers, perform STIR/SHAKEN actions, make destructive/irreversible changes, or enter financial/contractual/legal/regulatory commitments.
