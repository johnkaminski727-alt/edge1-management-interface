# Unified Communications — Current State

Last reconciled: 2026-08-18
Repository: `johnkaminski727-alt/edge1-management-interface`
Current merged implementation baseline: `7b959ebc0a3986673203a75d736b63596e3a4ddc`
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

Historical accepted subsystem PRs and commits remain intact; no shared history was rewritten.

## AI capability state

Fresh accepted live/read-only or local-prepare evidence includes:

- `communications.read` — historical accepted live evidence;
- `telephony.read` — historical accepted live evidence;
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

Phase 18 on 2026-08-18 completed the previously missing durable Messaging state requirement:

- the pre-restart in-memory event count was confirmed zero twice before the storage switch;
- exact repository/runtime source parity was confirmed against merged baseline `7b959ebc0a3986673203a75d736b63596e3a4ddc`;
- PostgreSQL 15.19 was installed with package autostart blocked until hardening completed;
- the cluster is local Unix-socket only with `listen_addresses = ''` and no TCP database listener;
- low-memory settings use 12 max connections, 32 MiB shared buffers, 1 MiB work memory, 16 MiB maintenance work memory, and JIT disabled;
- peer-authenticated local database access uses the existing `wwadmin` OS identity and no database password;
- database `wwcx_messaging` contains the exact repository migrations `0001_initial.sql` and `0002_control_state.sql`;
- `PostgresEventStore` ping, zero-event count, and initialized control state passed before restart;
- `/readyz` returned `storage: postgres` after restarting only the Messaging Gateway;
- live HTTP and database event counts matched at zero;
- PostgreSQL was enabled for reboot persistence only after functional acceptance;
- no SMS/MMS or carrier/provider routing was generated or changed.

Rollback:

`/tmp/edge1-uc-evidence-20260818T073658Z/rollback-messaging-postgres-20260818T111017Z.sh`

Messaging durable state is therefore `runtime_ready` and is no longer a global blocker.

## Fresh BigBird runtime

BigBird is freshly accepted as `0.3.4-alpha.3`, mode `read-only`, loopback on `127.0.0.1:8787`, with eight registry tools including `messages.conversation.read` and `messages.draft.prepare`. Missing scopes failed closed, an unsigned `/v1/chat` request returned HTTP `401`, messaging control remained disabled, and prepared drafts retained `prepared_not_sent`, `send_authorized: false`, and `mutation_authorized: false`.

No authorized model/chat request, SMS/MMS, email, call, or route change was generated for this acceptance.

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
- `config/communications/readiness-matrix-v1.json`.

The global `fresh_edge1_runtime_verified` flag remains `false`. Messaging durability and the canonical workspace feed are no longer blockers. Remaining safe-scope blockers are MMS trusted scanner/private storage, Mail correspondence lacking an authoritative native thread source, and fresh functional Voice/SIP acceptance if required for the final flag.

Operational warning: approximately 1.5 GiB memory remained available after Phase 18, while the configured 1 GiB swap allocation remained almost fully consumed. No recent OOM evidence was observed and PostgreSQL did not materially reduce available memory. Avoid unnecessary broad unrelated service restarts while host swap pressure remains unresolved.

## Remaining work categories

Remaining safe-scope work is narrow:

1. private MMS quarantine storage and trusted scanner integration with fail-closed verification;
2. `mail.correspondence.read` only after an authoritative native Mail Room correspondence source is explicitly selected and authorized;
3. fresh functional Voice/SIP read/status acceptance if required for the final global runtime flag;
4. final readiness/handoff reconciliation once those items are complete or explicitly blocked.

Separately controlled production/provider work remains blocked unless explicitly authorized.

## Production boundaries

Do not enable live SMS/MMS, originate calls, change emergency/SIP/carrier routes, enable live mail transmission, release quarantine, rotate/disclose credentials, change DNS/firewall/certificates/authentication policy, perform number porting or STIR/SHAKEN actions, or perform destructive/irreversible, financial, contractual, legal, or regulatory actions without the required separate authorization.
