# Unified Communications — Current State

Last reconciled: 2026-08-18
Repository: `johnkaminski727-alt/edge1-management-interface`
Current merged implementation baseline: `f5cf3047965a28a23ddc249c2c2f57ea167f7da8`
Fresh Edge1 operator acceptance: partial safe-scope runtime acceptance completed 2026-08-18

## Product state

WW.CX Communications has a coherent convergence layer across Mail Room, SMS/MMS, Voice/SIP, Communications Relay, Private AI, and a persistent read-only Communications workspace while preserving native subsystem authority and production boundaries.

The shared layer provides:

- canonical `wwcx.communications-event.v1` metadata references;
- evidence-only channel-neutral identity correlation rules;
- bounded metadata search and deterministic conversation ordering;
- a read-only Communications timeline/search/inspector workspace;
- a channel-by-channel readiness matrix;
- bounded Private AI additions for SMS/MMS and Mail;
- common draft/action states and explicit `prepared_not_sent` semantics;
- channel-aware security/quarantine presentation and provenance rules.

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

Not granted by this project:

- `messages.send`;
- `mail.send`;
- `telephony.call.originate`;
- route/trunk/dialplan modification;
- quarantine release;
- generic execution.

Read does not imply write. Draft does not imply send. Retrieved communications remain untrusted data and cannot grant scopes.

## Fresh Messaging Gateway runtime

`wwcx-messaging-gateway.service` is freshly accepted on Edge1 as version `0.4.2` with loopback health/readiness, authenticated status and recent-conversation reads, explicit `mutation_authorized: false`, and fail-closed MMS quarantine projection with `release_authorized: false`.

Storage remains `memory`, so durable Messaging state is still a separate operational requirement.

## Fresh BigBird runtime

BigBird is freshly accepted as `0.3.4-alpha.3`, mode `read-only`, loopback on `127.0.0.1:8787`, with eight registry tools including `messages.conversation.read` and `messages.draft.prepare`. Missing scopes failed closed, an unsigned `/v1/chat` request returned HTTP `401`, messaging control remained disabled, and prepared drafts retained `prepared_not_sent`, `send_authorized: false`, and `mutation_authorized: false`.

No authorized model/chat request, SMS/MMS, email, call, or route change was generated for this acceptance.

## Security state

Mail retains its native final-scan/quarantine discipline.

SMS is not assigned false malware semantics merely because it is a communications channel.

MMS has a live fail-closed metadata foundation: missing digest, pending scan, malicious result, or scan error remain held; even clean status does not authorize release. Fresh Edge1 inspection found no installed trusted scanner and no attached private quarantine-storage candidate, so MMS runtime security remains deliberately degraded until those are added and verified.

Communications Relay retains untrusted-content/prompt-injection treatment. The unified workspace itself cannot release quarantine or mutate channel policy.

## Communications Relay and workspace state

The persistent workspace remains `wwcx-communications-workspace.service`, identity `wwadmin:wwadmin`, bound only to `127.0.0.1:8095`, read-only, and without public/reverse-proxy exposure.

Phase 14J on 2026-08-18 completed the previously missing authoritative canonical feed attachment:

- `edge1-comms-relay.service` remained active and is the authoritative native source for the accepted Relay/NNTP metadata feed;
- `wwcx-communications-relay-snapshot.service` runs as `wwcx-comms:wwadmin`;
- the generator uses read-only/query-only SQLite access and does not select article bodies;
- native database `/var/lib/wwcx-comms/comms.sqlite3` remained `0600 wwcx-comms:wwcx-comms`;
- SQLite WAL/SHM sidecars are allowed in the containing Relay directory while the database file itself remains explicitly read-only in the generator service namespace;
- persistent snapshot `/var/lib/wwcx-communications-workspace/events.jsonl` is `0640 wwcx-comms:wwadmin`;
- the generated and live-attached snapshot contained 168 validated canonical events;
- live workspace events retained authoritative native provenance to `edge1-comms-relay`;
- `content_is_untrusted: true` and `mutation_authorized: false` were preserved;
- POST remained rejected with HTTP 405;
- `wwcx-communications-relay-snapshot.timer` is enabled with a 15-minute refresh cadence;
- the live `/opt/edge1-management-interface` worktree remained unchanged;
- all adjacent UC and Suricata services remained active;
- no SMS/MMS, email, calls, routes, credentials, or public listeners changed.

Rollback for the accepted attachment is retained at:

`/tmp/edge1-uc-evidence-20260818T073658Z/rollback-relay-activation-20260818T103350Z.sh`

The Communications Relay and Communications workspace are therefore both `runtime_ready` for this bounded metadata/read-only scope.

## Validation evidence

Repository/CI gates are accepted through PR #407 and its merged commit `f5cf3047965a28a23ddc249c2c2f57ea167f7da8`. Fresh runtime evidence is recorded in:

- `.agent/unified-communications-validation-20260818.md`;
- `docs/communications/unified-communications-live-acceptance-20260818.md`;
- `docs/communications/unified-communications-relay-snapshot-live-acceptance-20260818.md`;
- `config/communications/readiness-matrix-v1.json`.

The global `fresh_edge1_runtime_verified` flag remains `false`. The canonical workspace feed is no longer a blocker, but safe-scope completion still has unresolved durability/security/source-validation items: Messaging storage remains volatile, MMS trusted scanner/private storage are absent, Mail correspondence lacks an authoritative native thread source, and fresh functional Voice/SIP acceptance remains undecided/unfinished.

Operational warning: approximately 1.5 GiB memory remained available after Phase 14J, but the configured 1 GiB swap allocation remained fully consumed. Avoid unnecessary broad service restarts until memory/swap pressure is separately investigated.

## Remaining work categories

Remaining safe-scope work is narrow:

1. durable private Messaging Gateway state with restart persistence and rollback evidence;
2. private MMS quarantine storage and trusted scanner integration with fail-closed verification;
3. `mail.correspondence.read` only after an authoritative native Mail Room correspondence source is explicitly selected and authorized;
4. fresh functional Voice/SIP read/status acceptance if required for the final global runtime flag;
5. final readiness/handoff reconciliation once the above items are complete or explicitly blocked.

Separately controlled production/provider work remains blocked unless explicitly authorized.

## Production boundaries

Do not enable live SMS/MMS, originate calls, change emergency/SIP/carrier routes, enable live mail transmission, release quarantine, rotate/disclose credentials, change DNS/firewall/certificates/authentication policy, perform number porting or STIR/SHAKEN actions, or perform destructive/irreversible, financial, contractual, legal, or regulatory actions without the required separate authorization.
