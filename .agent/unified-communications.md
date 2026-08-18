# Unified Communications — Current State

Last reconciled: 2026-08-18
Repository: `johnkaminski727-alt/edge1-management-interface`
Repository completion baseline: `d7ccf2189a028df474ce5b7931870e10d6ec4292`
Fresh Edge1 operator acceptance: partial safe-scope runtime acceptance completed 2026-08-18

## Product state

WW.CX Communications has a coherent convergence layer across Mail Room, SMS/MMS, Voice/SIP, Communications Relay, Private AI, and a read-only Communications workspace while preserving native subsystem authority and production boundaries.

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

`/communications/` remains repository-ready as the daily read-only operator workspace. Fresh ephemeral Edge1 acceptance on port `8095` verified health/readiness, honest empty/no-snapshot behavior, mutation rejection via HTTP `405`, and successful rollback of the temporary listener.

Persistent deployment remains incomplete:

- `wwcx-communications-workspace.service` is not installed;
- port `8095` is free after ephemeral acceptance;
- an authoritative canonical runtime snapshot source is not attached;
- no public/reverse-proxy exposure is authorized by this acceptance.

## Validation evidence

Repository/CI gates remain accepted for PRs #384, #385, #386, #387, #389 and the final reconciliation PR #396.

Fresh runtime evidence is now separately recorded in:

- `.agent/unified-communications-validation-20260818.md`;
- `docs/communications/unified-communications-live-acceptance-20260818.md`;
- `config/communications/readiness-matrix-v1.json`.

The global `fresh_edge1_runtime_verified` flag remains `false` because the persistent Communications workspace and MMS scanner/private-storage runtime are still incomplete. This prevents partial subsystem acceptance from being overstated as full safe-scope runtime completion.

## Remaining work categories

Remaining safe-scope work is narrow:

1. persistent loopback-only Communications workspace service deployment and authoritative canonical snapshot attachment;
2. private MMS quarantine storage and trusted scanner integration with fail-closed verification;
3. `mail.correspondence.read` only after an authoritative native Mail Room correspondence source is explicitly selected and authorized;
4. final readiness/handoff reconciliation once the above items are complete or explicitly blocked.

Separately controlled production/provider work remains blocked unless explicitly authorized.

## Production boundaries

Do not enable live SMS/MMS, originate calls, change emergency/SIP/carrier routes, enable live mail transmission, release quarantine, rotate/disclose credentials, change DNS/firewall/certificates/authentication policy, perform number porting or STIR/SHAKEN actions, or perform destructive/irreversible, financial, contractual, legal, or regulatory actions without the required separate authorization.
