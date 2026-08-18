# WW.CX Unified Communications — Completion Handoff

Date: 2026-08-18
Repository: `johnkaminski727-alt/edge1-management-interface`
Primary private host: `edge1.ww.cx`
Current implementation baseline: `7b959ebc0a3986673203a75d736b63596e3a4ddc` plus fresh operator-run Edge1 acceptance

## Executive status

WW.CX Communications is substantially complete for the authorized safe scope. Mail Room, SMS/MMS, Voice/SIP, Communications Relay, Private AI, and the Communications operator workspace remain specialized systems, but share canonical metadata contracts, evidence-based identity rules, search/correlation semantics, readiness truth, AI capability boundaries, common draft/action states, provenance, and operator navigation.

Fresh Edge1 acceptance is complete for Messaging Gateway `0.4.2` including durable PostgreSQL state, BigBird `0.3.4-alpha.3`, bounded Mail AI status/draft behavior, the persistent loopback-only Communications workspace, and the authoritative Communications Relay/NNTP canonical snapshot feed.

Global `fresh_edge1_runtime_verified` remains false. Messaging durability and the canonical workspace feed are no longer blockers. Remaining safe-scope blockers are MMS trusted scanning/private quarantine storage, authoritative Mail correspondence source selection, and any required fresh functional Voice/SIP acceptance.

No production communication authority was added.

## Current live safe-scope state

### Messaging Gateway

- live `wwcx-messaging-gateway.service` version `0.4.2`;
- loopback health/readiness accepted;
- authenticated `messages.status.read` and `messages.conversation.read` accepted;
- conversation content marked untrusted and non-mutating;
- BigBird prepared replies remain local `prepared_not_sent` artifacts with no send authority;
- MMS quarantine metadata fail-closed with release unauthorized;
- Phase 18 switched the live gateway from `storage: memory` to `storage: postgres`;
- PostgreSQL 15.19 operates over the local Unix socket only with no TCP listener and no database password;
- repository migrations `0001_initial.sql` and `0002_control_state.sql` are applied to database `wwcx_messaging`;
- peer-authenticated least-privilege local database role uses the existing `wwadmin` OS identity;
- pre-restart in-memory event count was zero and post-restart HTTP/database event counts matched at zero;
- PostgreSQL is enabled for reboot persistence;
- no carrier traffic generated.

Messaging rollback:

`/tmp/edge1-uc-evidence-20260818T073658Z/rollback-messaging-postgres-20260818T111017Z.sh`

### Private AI / BigBird

- live BigBird version `0.3.4-alpha.3`, mode `read-only`, listener `127.0.0.1:8787`;
- eight read-only registry tools, including `messages.conversation.read` and `messages.draft.prepare`;
- missing-scope checks fail closed;
- prepared messaging drafts remain `prepared_not_sent`, `send_authorized: false`, `mutation_authorized: false`;
- messaging control remains disabled;
- unsigned `/v1/chat` returns HTTP 401.

### Mail AI

- `mail.status.read` accepted locally;
- `mail.draft.prepare` accepted with prepared-not-sent/no-send semantics;
- `mail.correspondence.read` remains blocked until an explicitly authorized authoritative native Mail Room correspondence source is selected.

### Communications Relay and workspace

Phase 14J remains the authoritative acceptance point for the shared read-only metadata plane:

- `edge1-comms-relay.service` active and retained as the authoritative native Relay/NNTP source;
- `wwcx-communications-relay-snapshot.service` accepted with identity `wwcx-comms:wwadmin`;
- native database `/var/lib/wwcx-comms/comms.sqlite3` retained as `0600 wwcx-comms:wwcx-comms`;
- database access remains read-only/query-only and article bodies are excluded from the canonical snapshot;
- SQLite WAL/SHM sidecars are allowed in the containing Relay directory while the database file itself is explicitly read-only inside the generator namespace;
- generated snapshot `/var/lib/wwcx-communications-workspace/events.jsonl` is `0640 wwcx-comms:wwadmin`;
- 168 canonical events generated, validated as the workspace user, and attached live;
- live response returned 168 events with authoritative native provenance;
- `content_is_untrusted: true` and `mutation_authorized: false` preserved;
- POST to the events API returned HTTP 405;
- workspace listener remained `127.0.0.1:8095` only;
- `wwcx-communications-relay-snapshot.timer` enabled with 15-minute refresh cadence;
- live repository worktree remained unchanged;
- adjacent UC services and Suricata remained active;
- no SMS/MMS, mail, calls, routes, credentials, quarantine release, or public listener changes occurred.

Relay/workspace rollback:

`/tmp/edge1-uc-evidence-20260818T073658Z/rollback-relay-activation-20260818T103350Z.sh`

Communications Relay and the Communications workspace are both `runtime_ready` for the bounded metadata/read-only scope.

### Voice/SIP

- Asterisk, Kamailio, telephony analytics, and telephony console active in fresh checks;
- `telephony.read` retains historical accepted read-only evidence;
- fresh CDR/CEL inspection found zero rows;
- no call origination, routing, dialplan, trunk, or emergency-calling mutation authority is inferred;
- final decision on whether another fresh functional Voice/SIP read/status acceptance is required remains open.

### MMS security runtime

- fail-closed metadata/quarantine foundation live;
- no trusted scanner attached;
- no private quarantine-storage runtime attached;
- trusted scanner/private storage therefore remain incomplete and security stays degraded;
- quarantine release remains unauthorized;
- durable PostgreSQL Messaging state does not change this separate security blocker.

## Merged repository milestones

- PR #384 — canonical event/identity/readiness/correlation core — `6b272fb0308bfeb161f50598845fc88b77e5c561`
- PR #385 — SMS/MMS Private AI read + draft — `ce5c561304a0a7aa109b887d1739ae90660b7633`
- PR #386 — Mail AI status + draft — `9e26ea6df6e0bc3469d3bc63701362b01a80bd94`
- PR #387 — Unified Communications workspace — `2b4550812cb6bc790cb3b3bc0d079bdfd261b220`
- PR #389 — fail-closed MMS quarantine foundation — `721d5e538835a4b53a05c2208e7940f1d83ec043`
- PR #396 — final repository reconciliation — `d7ccf2189a028df474ce5b7931870e10d6ec4292`
- PR #397 — fresh Edge1 runtime acceptance reconciliation — `6d2c24dfb756bbb735dabc4ffca51d9a6a8b73fc`
- PR #400 — hardened persistent Communications workspace deployment — `a46ec4433033648c3428ce061318cdaf347a3605`
- PR #404 — durable Relay canonical snapshot adapter — `78a4bc5563262f6da52e626a396248472b7852c7`
- PR #406 — Relay snapshot service identity correction — `c02cb3a1751d4b32768def32682bb150e90f308b`
- PR #407 — SQLite WAL/SHM sidecar sandbox correction — `f5cf3047965a28a23ddc249c2c2f57ea167f7da8`
- PR #408 — live Relay canonical snapshot acceptance reconciliation — `7b959ebc0a3986673203a75d736b63596e3a4ddc`

Repository CI and live-host acceptance are separate evidence. Green `Edge1 Operator Validation` workflow results are CI only; live claims above come from operator-run SSH acceptance.

## Resource state

Phase 18 completed with approximately 1.5 GiB memory available and no new OOM evidence, while the configured 1 GiB swap allocation remained almost fully consumed. PostgreSQL's bounded low-memory configuration did not materially reduce available memory. Avoid unnecessary broad unrelated restarts while swap pressure remains unresolved.

## Remaining safe-scope work

1. Attach private MMS quarantine storage with strict permissions/retention and a trusted scanner behind the existing fail-closed boundary. Clean results must remain held until a separately authorized release workflow exists.
2. Select and explicitly authorize an authoritative native Mail Room correspondence source before implementing `mail.correspondence.read`.
3. Perform fresh functional Voice/SIP read/status acceptance if required before setting the global runtime flag true.
4. Reconcile final readiness only when each remaining safe-scope layer has evidence or an explicit blocker.

## Production boundaries

The following remain separately controlled and are not authorized by Unified Communications completion:

- live SMS/MMS transmission;
- production mail send unless separately authorized;
- call origination;
- SIP/carrier/emergency route or dialplan mutation;
- quarantine release;
- credentials/key disclosure or rotation;
- DNS/firewall/certificate/authentication-policy changes;
- number porting or STIR/SHAKEN changes;
- provider financial/contractual actions;
- destructive or irreversible operations.

## Durable recovery points

- `.agent/unified-communications.md`
- `.agent/unified-communications-validation-20260818.md`
- `.agent/unified-communications-backlog-20260818.md`
- `config/communications/readiness-matrix-v1.json`
- `docs/communications/unified-communications-live-acceptance-20260818.md`
- `docs/communications/unified-communications-relay-snapshot-live-acceptance-20260818.md`
- `docs/communications/unified-communications-messaging-postgres-live-acceptance-20260818.md`
- this handoff document

These records let the next operator continue from verified evidence rather than reconstructing project state from memory.
