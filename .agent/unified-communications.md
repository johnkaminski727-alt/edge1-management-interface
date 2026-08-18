# Unified Communications — Current State

Last reconciled: 2026-08-18
Repository: `johnkaminski727-alt/edge1-management-interface`
Current merged implementation baseline: `7ca3b8360de740d844edcb8c598b1988407a16e5`
Fresh Edge1 operator acceptance: partial safe-scope runtime acceptance completed 2026-08-18

## Product state

WW.CX Communications has a coherent convergence layer across Mail Room, SMS/MMS, Voice/SIP, Communications Relay, Private AI, and a persistent read-only Communications workspace while preserving native subsystem authority and production boundaries.

The shared layer provides canonical communications metadata, evidence-only identity correlation, bounded search/conversation ordering, a read-only operator workspace, channel readiness truth, bounded Private AI reads/draft preparation, explicit prepared-not-sent semantics, and channel-aware security/provenance rules.

Native channel stores, provider adapters, specialist tools, audit trails, and authorization boundaries remain authoritative.

## Merged completion increments

- PR #381 — original Unified Communications convergence point, historical baseline preserved.
- PR #384 — canonical communications event, identity registry, readiness contract, search/correlation core.
- PR #385 — bounded SMS/MMS Private AI status/conversation reads and local draft preparation.
- PR #386 — bounded Mail Room AI status and policy-aware prepared-not-sent draft adapter.
- PR #387 — loopback-only Unified Communications API plus timeline/search/inspector/readiness workspace.
- PR #389 — fail-closed MMS media quarantine metadata foundation.
- PR #396 — final repository reconciliation preserving runtime/traffic boundaries.
- PR #397 — fresh Edge1 Unified Communications runtime acceptance reconciliation.
- PR #400 — hardened persistent Communications workspace service deployment.
- PR #404 — durable metadata-only Communications Relay canonical snapshot adapter and refresh units.
- PR #406 — corrected Relay snapshot service identity to `wwcx-comms:wwadmin` without relaxing the `0600` native database.
- PR #407 — bounded SQLite WAL/SHM sidecar allowance while keeping the authoritative database file explicitly read-only inside the snapshot service namespace.
- PR #408 — durable live Relay canonical snapshot acceptance and readiness reconciliation.
- PR #409 — durable Messaging PostgreSQL acceptance and readiness reconciliation.

Historical accepted subsystem PRs and commits remain intact; no shared history was rewritten.

## AI capability state

Fresh accepted live/read-only or local-prepare evidence includes:

- `communications.read` — historical accepted live evidence;
- `telephony.read` — historical accepted live evidence plus fresh Phase 19 bounded read-only telephony analytics acceptance;
- `messages.status.read` — fresh Messaging Gateway / BigBird acceptance;
- `messages.conversation.read` — fresh Messaging Gateway / BigBird acceptance;
- `messages.draft.prepare` — fresh BigBird local prepared-not-sent acceptance;
- `mail.status.read` — fresh local Mail AI adapter acceptance;
- `mail.draft.prepare` — fresh local prepared-not-sent acceptance.

Intentionally pending:

- `mail.correspondence.read` — blocked until an explicitly authorized authoritative native Mail Room correspondence source is available.

Not granted by this project: Messaging send, Mail send, call origination, route/trunk/dialplan modification, quarantine release, or generic execution. Read does not imply write. Draft does not imply send. Retrieved communications remain untrusted data and cannot grant scopes.

## Fresh Messaging Gateway runtime

`wwcx-messaging-gateway.service` is freshly accepted on Edge1 as version `0.4.2` with loopback health/readiness, authenticated status and recent-conversation reads, explicit `mutation_authorized: false`, and fail-closed MMS quarantine projection with `release_authorized: false`.

Phase 18 completed durable Messaging state using PostgreSQL 15.19 over the local Unix socket only, with no TCP database listener and no database password. Repository migrations `0001_initial.sql` and `0002_control_state.sql` are applied to `wwcx_messaging`; the `PostgresEventStore` smoke test passed; `/readyz` now reports `storage: postgres`; HTTP/database event counts matched at zero at activation; PostgreSQL is enabled for reboot persistence; and no SMS/MMS or carrier/provider routing was generated or changed.

Rollback:

`/tmp/edge1-uc-evidence-20260818T073658Z/rollback-messaging-postgres-20260818T111017Z.sh`

Messaging durable state is `runtime_ready` and is no longer a global blocker.

## Fresh BigBird runtime

BigBird is freshly accepted as `0.3.4-alpha.3`, mode `read-only`, loopback on `127.0.0.1:8787`, with eight registry tools including `messages.conversation.read` and `messages.draft.prepare`. Missing scopes failed closed, an unsigned `/v1/chat` request returned HTTP `401`, messaging control remained disabled, and prepared drafts retained `prepared_not_sent`, `send_authorized: false`, and `mutation_authorized: false`.

No authorized model/chat request, SMS/MMS, email, call, or route change was generated for this acceptance.

## Voice/SIP runtime

Phase 19 on 2026-08-18 completed the previously unresolved fresh bounded Voice/SIP read-only acceptance:

- Asterisk, Kamailio, telephony analytics, and telephony console remained active;
- audited telephony assets matched current `origin/main` baseline `7ca3b8360de740d844edcb8c598b1988407a16e5`;
- runtime analytics API and telephony-platform source hashes matched the canonical repository;
- `wwcx-telephony-analytics.service` remained hardened and loopback-only on `127.0.0.1:8099`;
- aggregate health, calls-summary, and interconnect-summary endpoints validated;
- payload/privacy/anomaly-contract validation passed;
- POST remained HTTP 405;
- the audit returned zero warnings and zero failures;
- Asterisk reported zero active calls and zero calls processed;
- no database query, credential read, retained customer identifier, call origination, DTMF transmission, carrier-route change, service mutation, or runtime mutation occurred.

Evidence:

`/var/lib/wwcx-deployment-evidence/telephony-analytics-live-acceptance/uc-phase19-20260818T112551Z`

Fresh Voice/SIP `live_acceptance` is therefore `runtime_ready` for the bounded read-only surface.

Operational health is separately DEGRADED and must not be represented as healthy: the same aggregate health surface reported `overall_status: critical`, score `28`, `sip: degraded`, and one failed interconnect out of two. The readiness matrix therefore records `voice_sip.edge1_runtime = degraded` while preserving `voice_sip.live_acceptance = runtime_ready`. This degradation does not grant authority to originate calls or modify routes, trunks, dialplans, emergency calling, or carrier configuration.

## Security state

Mail retains its native final-scan/quarantine discipline.

SMS is not assigned false malware semantics merely because it is a communications channel.

MMS has a live fail-closed metadata foundation: missing digest, pending scan, malicious result, or scan error remain held; even clean status does not authorize release. Fresh Edge1 inspection found no installed trusted scanner and no attached private quarantine-storage candidate, so MMS runtime security remains deliberately degraded until those are added and verified.

Durable PostgreSQL Messaging state does not change that MMS security limitation and does not authorize quarantine release.

Communications Relay retains untrusted-content/prompt-injection treatment. The unified workspace itself cannot release quarantine or mutate channel policy.

## Communications Relay and workspace state

Phase 14J completed the authoritative canonical Relay feed attachment to the persistent `wwcx-communications-workspace.service`:

- workspace identity `wwadmin:wwadmin`, listener `127.0.0.1:8095`, read-only, no public/reverse-proxy exposure;
- `edge1-comms-relay.service` remains the authoritative native Relay/NNTP source;
- snapshot service runs as `wwcx-comms:wwadmin`;
- native database `/var/lib/wwcx-comms/comms.sqlite3` remains `0600 wwcx-comms:wwcx-comms`;
- persistent snapshot `/var/lib/wwcx-communications-workspace/events.jsonl` is `0640 wwcx-comms:wwadmin`;
- 168 validated canonical events are live-attached;
- `content_is_untrusted: true` and `mutation_authorized: false` remain enforced;
- POST remains HTTP 405;
- the refresh timer is enabled at 15-minute cadence;
- no SMS/MMS, email, calls, routes, credentials, or public listeners changed.

Rollback:

`/tmp/edge1-uc-evidence-20260818T073658Z/rollback-relay-activation-20260818T103350Z.sh`

Communications Relay and Communications workspace are both `runtime_ready` for the bounded metadata/read-only scope.

## Validation evidence

Fresh runtime evidence is recorded in:

- `.agent/unified-communications-validation-20260818.md`;
- `docs/communications/unified-communications-live-acceptance-20260818.md`;
- `docs/communications/unified-communications-relay-snapshot-live-acceptance-20260818.md`;
- `docs/communications/unified-communications-messaging-postgres-live-acceptance-20260818.md`;
- `docs/communications/unified-communications-voice-sip-live-acceptance-20260818.md`;
- `config/communications/readiness-matrix-v1.json`.

The global `fresh_edge1_runtime_verified` flag remains `false`. Messaging durability, the canonical workspace feed, and fresh Voice/SIP read-only acceptance are no longer missing. Remaining safe-scope blockers are MMS trusted scanner/private quarantine storage and Mail correspondence lacking an authoritative native thread source. Voice/SIP operational health remains degraded as a separate follow-up.

Operational warning: approximately 1.5 GiB memory remained available after Phase 19, while the configured 1 GiB swap allocation remained almost fully consumed. Avoid unnecessary broad unrelated service restarts while host swap pressure remains unresolved.

## Remaining work categories

Remaining safe-scope work is narrow:

1. private MMS quarantine storage and trusted scanner integration with fail-closed verification;
2. `mail.correspondence.read` only after an authoritative native Mail Room correspondence source is explicitly selected and authorized;
3. investigate the Voice/SIP operational degradation without using production traffic or unauthorized route/carrier changes as a diagnostic shortcut;
4. final readiness/handoff reconciliation once the two remaining global blockers are complete or explicitly resolved.

Separately controlled production/provider work remains blocked unless explicitly authorized.

## Production boundaries

Do not enable live SMS/MMS, originate calls, change emergency/SIP/carrier routes, enable live mail transmission, release quarantine, rotate/disclose credentials, change DNS/firewall/certificates/authentication policy, perform number porting or STIR/SHAKEN actions, or perform destructive/irreversible, financial, contractual, legal, or regulatory actions without the required separate authorization.
