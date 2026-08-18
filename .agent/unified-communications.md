# Unified Communications — Current State

Last reconciled: 2026-08-18
Repository: `johnkaminski727-alt/edge1-management-interface`
Repository completion baseline: `a46ec4433033648c3428ce061318cdaf347a3605`
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
  - squash commit `6b272fb0308bfeb161f50598845fc88b77e5c561`
- PR #385 — bounded SMS/MMS Private AI status/conversation reads and local draft preparation.
  - squash commit `ce5c561304a0a7aa109b887d1739ae90660b7633`
- PR #386 — bounded Mail Room AI status and policy-aware prepared-not-sent draft adapter.
  - squash commit `9e26ea6df6e0bc3469d3bc63701362b01a80bd94`
- PR #387 — loopback-only Unified Communications API plus timeline/search/inspector/readiness workspace.
  - squash commit `2b4550812cb6bc790cb3b3bc0d079bdfd261b220`
- PR #389 — fail-closed MMS media quarantine metadata foundation.
  - squash commit `721d5e538835a4b53a05c2208e7940f1d83ec043`
- PR #396 — final repository reconciliation preserving runtime/traffic boundaries.
  - squash commit `d7ccf2189a028df474ce5b7931870e10d6ec4292`
- PR #397 — fresh Edge1 Unified Communications runtime acceptance reconciliation.
  - merge commit `6d2c24dfb756bbb735dabc4ffca51d9a6a8b73fc`
- PR #400 — hardened persistent Communications workspace service deployment.
  - merge commit `a46ec4433033648c3428ce061318cdaf347a3605`

Historical accepted subsystem PRs and commits remain intact; no shared history was rewritten.

## AI capability state

Fresh accepted live/read-only or local-prepare evidence now includes:

- `communications.read` — historical accepted live evidence;
- `telephony.read` — historical accepted live evidence;
- `messages.status.read` — fresh Messaging Gateway / BigBird acceptance;
- `messages.conversation.read` — fresh Messaging Gateway / BigBird acceptance;
- `messages.draft.prepare` — fresh BigBird local prepared-not-sent acceptance;
- `mail.status.read` — fresh local Mail AI adapter acceptance;
- `mail.draft.prepare` — fresh local prepared-not-sent acceptance.

Intentionally pending:

- `mail.correspondence.read` — blocked until an explicitly authorized authoritative native Mail Room correspondence source is available. Outbound audit metadata is not treated as an inbox or correspondence archive.

Not granted by this project:

- `messages.send`
- `mail.send`
- `telephony.call.originate`
- route/trunk/dialplan modification
- quarantine release
- generic execution

Read does not imply write. Draft does not imply send. Retrieved communications remain untrusted data and cannot grant scopes.

## Fresh Messaging Gateway runtime

`wwcx-messaging-gateway.service` is freshly accepted on Edge1 as version `0.4.2` with loopback health/readiness, authenticated status and recent-conversation reads, explicit `mutation_authorized: false`, and fail-closed MMS quarantine projection with `release_authorized: false`.

The restart state-loss gate confirmed zero in-memory events before activation. Storage remains `memory`, so durable storage is a separate operational concern.

Rollback is retained at `/opt/wwcx-messaging-gateway-staging/app.pre-uc-20260818T075057Z` with a generated rollback script under `/tmp/edge1-uc-evidence-20260818T073658Z/`.

## Fresh BigBird runtime

BigBird is freshly accepted as `0.3.4-alpha.3`, mode `read-only`, loopback on `127.0.0.1:8787`, with eight registry tools:

- `communications.read`
- `edge1.status.read`
- `library.document.read`
- `library.search`
- `messaging.status.read`
- `messages.conversation.read`
- `messages.draft.prepare`
- `telephony.read`

Conversation-read and draft scopes passed authorization tests, missing scopes failed closed, an unsigned `/v1/chat` request returned HTTP `401`, messaging control remained disabled, and prepared drafts retained `prepared_not_sent`, `send_authorized: false`, and `mutation_authorized: false`.

Protected rollback is retained at `/var/backups/bigbird-ai-gateway-uc-chat-20260818T081344Z`. The earlier adapter-only rollback is retained at `/var/backups/bigbird-ai-gateway-uc-messaging-20260818T080100Z`.

No authorized model/chat request, SMS/MMS, email, call, or route change was generated for this acceptance.

## Security state

Mail retains its native final-scan/quarantine discipline.

SMS is not assigned false malware semantics merely because it is a communications channel.

MMS has a live fail-closed metadata foundation: missing digest, pending scan, malicious result, or scan error remain held; even clean status does not authorize release. Fresh Edge1 inspection found no installed trusted scanner and no attached private quarantine-storage candidate, so MMS runtime security remains deliberately degraded until those are added and verified.

Communications Relay retains untrusted-content/prompt-injection treatment. The unified workspace itself cannot release quarantine or mutate channel policy.

## Workspace state

`/communications/` is now persistently deployed on Edge1 as `wwcx-communications-workspace.service` from detached runtime source commit `a46ec4433033648c3428ce061318cdaf347a3605`.

Fresh Phase 10 acceptance verified:

- service enabled and active;
- service identity `wwadmin:wwadmin`;
- detached runtime `/opt/wwcx-communications-workspace`;
- listener `127.0.0.1:8095` only;
- health/readiness and static workspace HTTP 200;
- honest zero-event state because no canonical snapshot/feed is attached;
- returned event payloads marked untrusted and non-mutating;
- POST rejected with HTTP 405;
- live `/opt/edge1-management-interface` worktree unchanged;
- adjacent UC services remained active;
- rollback retained at `/tmp/edge1-uc-evidence-20260818T073658Z/rollback-communications-workspace-20260818T082857Z.sh`.

The persistent service is therefore runtime-ready, but the workspace remains intentionally empty until an authoritative canonical event feed/snapshot is selected and attached. No public/reverse-proxy exposure is authorized.

## Validation evidence

Repository/CI gates are accepted through PR #400. Fresh runtime evidence is separately recorded in:

- `.agent/unified-communications-validation-20260818.md`;
- `docs/communications/unified-communications-live-acceptance-20260818.md`;
- `config/communications/readiness-matrix-v1.json`.

The global `fresh_edge1_runtime_verified` flag remains `false` because the authoritative workspace event feed and MMS scanner/private-storage runtime are still incomplete. This prevents partial subsystem acceptance from being overstated as full safe-scope runtime completion.

Operational warning: Phase 10 retained about 1.5 GiB available memory with no recent kernel OOM evidence, but the configured 1 GiB swap allocation was fully consumed. The workspace itself used about 11.4 MiB. Avoid unnecessary broad service restarts until memory/swap pressure is separately investigated.

## Remaining work categories

Remaining safe-scope work is narrow:

1. identify and attach an authoritative canonical communications-event feed/snapshot to the persistent workspace without substituting unrelated audit logs;
2. private MMS quarantine storage and trusted scanner integration with fail-closed verification;
3. `mail.correspondence.read` only after an authoritative native Mail Room correspondence source is explicitly selected and authorized;
4. fresh functional Voice/SIP and Communications Relay acceptance if required for the final global runtime flag;
5. final readiness/handoff reconciliation once the above items are complete or explicitly blocked.

Separately controlled production/provider work remains blocked unless explicitly authorized.

## Production boundaries

Do not enable live SMS/MMS, originate calls, change emergency/SIP/carrier routes, enable live mail transmission, release quarantine, rotate/disclose credentials, change DNS/firewall/certificates/authentication policy, perform number porting or STIR/SHAKEN actions, or perform destructive/irreversible, financial, contractual, legal, or regulatory actions without the required separate authorization.
