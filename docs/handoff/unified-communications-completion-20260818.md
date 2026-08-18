# WW.CX Unified Communications — Completion Handoff

Date: 2026-08-18
Repository: `johnkaminski727-alt/edge1-management-interface`
Primary private host: `edge1.ww.cx`
Repository/runtime baseline: `a46ec4433033648c3428ce061318cdaf347a3605` plus fresh operator-run Edge1 acceptance

## Executive status

WW.CX Communications is substantially complete for the authorized safe scope. Mail Room, SMS/MMS, Voice/SIP, Communications Relay, Private AI, and the Communications operator workspace remain specialized systems, but share canonical metadata contracts, evidence-based identity rules, search/correlation semantics, readiness truth, AI capability boundaries, common draft/action states, provenance, and operator navigation.

Fresh Edge1 acceptance has now been completed for Messaging Gateway `0.4.2`, BigBird `0.3.4-alpha.3`, bounded Mail AI status/draft behavior, and the persistent loopback-only Communications workspace. No production communication authority was added.

Global `fresh_edge1_runtime_verified` remains false because the persistent workspace still has no authoritative canonical event feed/snapshot attached and MMS trusted scanning/private quarantine storage remain incomplete. Historical Voice/SIP and Relay reads remain accepted, but fresh service-active evidence alone is not promoted to new functional acceptance.

## Current live safe-scope state

### Messaging Gateway

- live `wwcx-messaging-gateway.service` version `0.4.2`;
- loopback health/readiness accepted;
- authenticated `messages.status.read` and `messages.conversation.read` accepted;
- conversation content marked untrusted and non-mutating;
- MMS quarantine metadata is fail-closed with release unauthorized;
- storage remains `memory`;
- rollback retained at `/opt/wwcx-messaging-gateway-staging/app.pre-uc-20260818T075057Z` plus evidence rollback script.

### Private AI / BigBird

- live BigBird version `0.3.4-alpha.3`, mode `read-only`, listener `127.0.0.1:8787`;
- eight read-only registry tools, preserving the original six and adding `messages.conversation.read` and `messages.draft.prepare`;
- missing-scope checks fail closed;
- prepared messaging drafts remain `prepared_not_sent`, `send_authorized: false`, `mutation_authorized: false`;
- messaging control remains disabled;
- unsigned `/v1/chat` returns HTTP 401;
- rollback retained at `/var/backups/bigbird-ai-gateway-uc-chat-20260818T081344Z` and `/var/backups/bigbird-ai-gateway-uc-messaging-20260818T080100Z`.

### Mail AI

- `mail.status.read` accepted locally;
- `mail.draft.prepare` accepted with prepared-not-sent/no-send semantics;
- `mail.correspondence.read` remains blocked until an explicitly authorized authoritative native Mail Room correspondence source is selected.

### Communications workspace

- persistent `wwcx-communications-workspace.service` installed, enabled, active, and running;
- detached runtime `/opt/wwcx-communications-workspace` from exact source commit `a46ec4433033648c3428ce061318cdaf347a3605`;
- service identity `wwadmin:wwadmin`;
- listener `127.0.0.1:8095` only;
- health/readiness/static workspace HTTP 200;
- event API returns an honest zero-event state because no canonical feed/snapshot is attached;
- event responses remain untrusted and `mutation_authorized: false`;
- POST/PUT/PATCH/DELETE remain rejected; tested POST returned HTTP 405;
- no reverse proxy or public listener added;
- live `/opt/edge1-management-interface` worktree remained unchanged by deployment;
- rollback retained at `/tmp/edge1-uc-evidence-20260818T073658Z/rollback-communications-workspace-20260818T082857Z.sh`.

Operational warning: Phase 10 showed about 1.5 GiB available memory and no recent kernel OOM evidence, but the configured 1 GiB swap allocation was fully consumed. The workspace used about 11.4 MiB. Avoid unnecessary broad restarts until memory/swap pressure is separately understood.

### Voice/SIP and Communications Relay

- Asterisk, Kamailio, telephony analytics, telephony console, and `edge1-comms-relay.service` were active in fresh service checks;
- `telephony.read` and `communications.read` retain historical accepted read-only evidence;
- no call origination, routing, dialplan, upstream-posting, or other mutation authority is inferred.

### MMS security runtime

- fail-closed metadata/quarantine foundation is live;
- no installed `clamscan`, `clamdscan`, or `freshclam` was found;
- no active ClamAV service/socket was found;
- no candidate private quarantine-storage directory was found in the inspected `/var/lib`, `/srv`, or `/opt` paths;
- trusted scanner/private storage therefore remain incomplete and security stays degraded;
- quarantine release remains unauthorized.

## Merged repository milestones

- PR #384 — canonical event/identity/readiness/correlation core — `6b272fb0308bfeb161f50598845fc88b77e5c561`
- PR #385 — SMS/MMS Private AI read + draft — `ce5c561304a0a7aa109b887d1739ae90660b7633`
- PR #386 — Mail AI status + draft — `9e26ea6df6e0bc3469d3bc63701362b01a80bd94`
- PR #387 — Unified Communications workspace — `2b4550812cb6bc790cb3b3bc0d079bdfd261b220`
- PR #389 — fail-closed MMS quarantine foundation — `721d5e538835a4b53a05c2208e7940f1d83ec043`
- PR #396 — final repository reconciliation — `d7ccf2189a028df474ce5b7931870e10d6ec4292`
- PR #397 — fresh Edge1 runtime acceptance reconciliation — `6d2c24dfb756bbb735dabc4ffca51d9a6a8b73fc`
- PR #400 — hardened persistent Communications workspace deployment — `a46ec4433033648c3428ce061318cdaf347a3605`

Repository CI and live-host acceptance are separate evidence. Green `Edge1 Operator Validation` workflow results are CI only; live claims above come from operator-run SSH acceptance.

## Remaining safe-scope work

1. Identify the authoritative native source(s) that can produce canonical `wwcx.communications-event.v1` metadata and attach a bounded feed/snapshot to the persistent workspace. Do not substitute unrelated audit logs or fabricate events.
2. Attach private MMS quarantine storage with strict permissions/retention and a trusted scanner behind the existing fail-closed boundary. Clean results must remain held until a separately authorized release workflow exists.
3. Select and explicitly authorize an authoritative native Mail Room correspondence source before implementing `mail.correspondence.read`.
4. Perform fresh functional Voice/SIP and Relay read-only acceptance if required before setting the global runtime flag true.
5. Reconcile final readiness only when each remaining safe-scope layer has evidence.

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
- this handoff document

These records are intended to let the next operator continue from verified evidence rather than reconstructing project state from memory.
