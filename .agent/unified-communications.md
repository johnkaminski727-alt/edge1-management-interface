# Unified Communications — Current State

Last reconciled: 2026-08-18, Phase 28 implementation
Repository: `johnkaminski727-alt/edge1-management-interface`
Phase 28 branch base: `9711461125a73f013b0f0a09347a6b1d1105eb5f`
Global `fresh_edge1_runtime_verified`: **false**

## Current truth

WW.CX Communications remains read-only/non-sending by default. Existing fresh Edge1 acceptance for Messaging/PostgreSQL, BigBird Messaging reads/drafts, the Communications workspace/Relay feed, Mail status/draft preparation, and bounded Voice/SIP reads remains intact. No Phase 28 claim expands production communications authority.

`main` advanced after Phase 27 through PR #426, which added a fail-closed durable outbound Messaging queue. Phase 28 was based on that newer main and does not alter the unrelated SNMP or other parallel work.

## Phase 28 — functional local Mail correspondence

Phase 28 closes the repository/software-functionality gap that remained after the Phase 27 storage foundation.

Implemented chain:

`local RFC822 file -> bounded native parser -> private SQLite store -> authenticated loopback Mail API -> BigBird Mail facade -> mail.correspondence.read`

### Local native source

`server/mail_local_rfc822_source.py`:

- accepts only bounded local RFC822 bytes/files;
- performs no network activity;
- requires canonical `Message-ID` and timezone-bearing `Date`;
- preserves explicit `In-Reply-To` / `References` relationships;
- preserves optional native/provider message and thread IDs when supplied;
- persists only bounded `text/plain` content and ignores attachment bytes;
- does not infer threads from subject/name similarity;
- records source `local-mailroom-rfc822`, scope `local_native`, authoritative `true`;
- marks returned message content untrusted and grants no send/mutation authority.

`tools/mail_local_intake.py` is the operator intake entry point. Runtime database location is constrained to `/var/lib/wwcx-mail-room` and is not emitted in API status projections.

### Persisted provenance/read boundary

`server/mail_correspondence_store.py` now persists immutable `source_scope` as well as source/authority. Readable authoritative scopes are only `local_native` and `production_native`. Synthetic records cannot claim authority, cannot be upgraded by reopening the database, and are rejected by the Private AI read adapter. Read-only mode opens SQLite with `mode=ro` and rejects writes.

### Mail AI and loopback API

`server/mail_ai_adapter.py` now supports bounded individual-message and thread reads. Reads are disabled by default and fail closed unless:

1. correspondence reading is explicitly enabled;
2. the private store exists and has safe permissions/schema;
3. the requested record carries persisted `authoritative=true` provenance;
4. the persisted scope is `local_native` or `production_native`.

Local-native readiness is explicitly `production_provider_ready=false` and `source_truth=local_native_only`.

`server/outbound_mail_gateway_server.py` exposes authenticated read-only endpoints behind the existing HMAC/replay-protected loopback API:

- `/outbound-mail/api/v1/correspondence/status`;
- `/outbound-mail/api/v1/correspondence/message/<encoded-message-id>`;
- `/outbound-mail/api/v1/correspondence/thread/<encoded-thread-id>`.

The public unauthenticated status surface does not expose correspondence data or the private database path.

### BigBird repository integration

Phase 28 adds:

- `integrations/bigbird_mail/client.py`;
- `integrations/bigbird_mail/tools.py`;
- `integrations/bigbird-mail/tool-manifest.json`.

The client is loopback-only and HMAC-authenticated. The tool facade re-checks untrusted-content, no-send/non-mutation state and immutable authoritative provenance before returning Mail content. There is no `send` method. Draft preparation remains `prepared_not_sent`.

The dedicated proposed runtime client ID is `wwcx-private-ai`, but Phase 28 intentionally does **not** modify the deployed/base HMAC allowed-client policy. Registering a new live client is an authentication-policy change and remains separately controlled.

## Functional acceptance

`tests/validate_mail_correspondence_functional.py` provides a complete local acceptance path using only generated local messages:

- root RFC822 ingest;
- reply RFC822 ingest and explicit thread reconstruction;
- provider/native ID preservation;
- private file/directory permissions;
- HTML-only body fail-closed behavior;
- synthetic-record isolation;
- arbitrary runtime DB path rejection;
- direct Mail AI message/thread reads;
- unsigned API rejection;
- HMAC-authenticated API message/thread reads;
- BigBird facade reads;
- untrusted prompt-like body handling;
- prepared-not-sent draft behavior;
- no production authentication-policy mutation in the test.

Exact-head GitHub CI is the authoritative repository validation gate and must pass before merge.

## MMS runtime

Repository-side MMS security remains ready for live acceptance from Phase 27: private content-addressed quarantine store, fixed `/usr/bin/clamscan` adapter, and local clean/EICAR/failure/restart acceptance tooling.

Live Edge1 acceptance is still unavailable in this session because no authenticated Edge1 shell/execution connector is exposed and the local container has no SSH execution identity. Therefore no package installation, private-root creation, Messaging restart, live scanner test, or live rollback evidence is claimed. SMS/MMS `security_quarantine` remains `degraded` until those checks actually run.

## Mail production/provider status

The local-native path is functional software, but it is not a claim that a provider mailbox is connected. Current provider inventory still does not prove an authoritative provider-side mailbox/thread source for the canonical Mail Room addresses.

`mail.correspondence.read` is therefore:

- repository-functional for explicit local-native records;
- pending live Edge1 acceptance;
- pending authentication-policy approval for a dedicated live BigBird client;
- pending a `production_native` source before any provider-production correspondence claim.

No outbound audit metadata is treated as correspondence.

## Existing shared runtime truth

- Messaging Gateway/PostgreSQL: previously `runtime_ready`; no live SMS/MMS authority.
- BigBird: previously `runtime_ready` for accepted Messaging/communications/telephony scopes; Phase 28 Mail tools not yet live-registered.
- Communications workspace/Relay: previously `runtime_ready`, loopback-only, authoritative Relay metadata feed attached.
- Voice/SIP: bounded read-only acceptance `runtime_ready`; current external interconnect health remains `unknown`, because the prior degraded display came from a stored 2026-07-20 status snapshot rather than a fresh live probe.

## Remaining blockers

1. **Authenticated Edge1 execution path** — required for live MMS scanner/private-root deployment and acceptance, local Mail deployment, service/listener/permission/restart checks, and rollback evidence.
2. **Authentication-policy approval** — required before registering `wwcx-private-ai` as a live HMAC client on the existing Mail gateway.
3. **Production-native Mail source** — required only for provider-production correspondence readiness; local-native software functionality does not depend on it.

`fresh_edge1_runtime_verified` remains false.

## Production boundaries

Without separate explicit authorization, do not send live SMS/MMS or email, originate production calls, change emergency/SIP/carrier routing, modify DNS/firewall/certificates/authentication policy, rotate/disclose credentials, release quarantine, port numbers, perform STIR/SHAKEN actions, make destructive/irreversible changes, or enter financial/contractual/legal/regulatory commitments.
