# Unified Communications — Current State

Last reconciled: 2026-08-18, Phase 27 closeout
Repository: `johnkaminski727-alt/edge1-management-interface`
Phase 27 merged PR: #424
Current Phase 27 repository baseline: `d01a2620c8d252260391cc9a2f86ec32938c146c`
Global `fresh_edge1_runtime_verified`: **false**

## Product state

WW.CX Communications has a coherent convergence layer across Mail Room, SMS/MMS, Voice/SIP, Communications Relay, Private AI, and a persistent read-only Communications workspace while preserving native subsystem authority and production boundaries.

Accepted safe-scope capabilities include canonical communications metadata, evidence-only identity correlation, bounded search/conversation ordering, a read-only operator workspace, channel readiness truth, Messaging status/conversation reads, local prepared-not-sent Messaging drafts, Mail status, local prepared-not-sent Mail drafts, bounded Voice/SIP read-only analytics, and the authoritative Communications Relay canonical metadata feed.

No project state grants live Messaging send, Mail send, call origination, route/trunk/dialplan mutation, quarantine release, generic execution, credential access, or production/provider authorization.

## Current repository baseline and parallel work

Phase 27 began from `main` `967096132bc5f998d68893ff43c81ffc3f37e2b5`, which already included Secure MCP Tunnel work newer than the Phase 26 recovery point. PR #424 merged the Phase 27 repository implementation as `d01a2620c8d252260391cc9a2f86ec32938c146c` after exact-head WW.CX Messaging Gateway, Validate repository, and Edge1 Operator Validation workflows all passed. Active SNMP and other parallel branches remain unrelated and must not be reset, overwritten, or folded into Unified Communications work.

## Messaging and MMS

Fresh accepted live Messaging state from earlier 2026-08-18 phases remains:

- `wwcx-messaging-gateway.service` version `0.4.2`;
- loopback health/readiness;
- authenticated `messages.status.read` and `messages.conversation.read`;
- durable PostgreSQL state over a local Unix socket;
- no PostgreSQL TCP listener and no database password;
- BigBird `messages.draft.prepare` remains local `prepared_not_sent` with no send/mutation authority;
- provider media URLs remain excluded from sanitized operator/AI projections;
- quarantine release remains false.

Phase 26 established repository-side content-addressed private MMS quarantine storage with bounded ingest, SHA-256 verification, `0700` directories, `0600` files, integrity checks, restart recovery, retention-held semantics, audit state, and a narrow `TrustedMediaScanner` contract.

Phase 27 merged:

- `services/wwcx-messaging-gateway/app/trusted_scanner.py` — a concrete local ClamAV adapter fixed to `/usr/bin/clamscan` and fixed non-destructive options;
- bounded timeout/unavailable/non-verdict behavior through the existing fail-closed scan boundary;
- no caller-controlled arbitrary executable/options and no cloud scanner path;
- `services/wwcx-messaging-gateway/scripts/private-quarantine-acceptance.py` — local synthetic clean/EICAR/restart acceptance only.

**Runtime status is still incomplete.** This session had no authenticated Edge1 execution connector, so it did not prove ClamAV/signatures are installed, create the live private quarantine root, execute synthetic live acceptance, restart Messaging, or verify live ownership/listeners/rollback. SMS/MMS `security_quarantine` therefore remains `degraded` despite the now-merged repository adapter.

Runtime procedure: `docs/communications/unified-communications-phase27-runtime-acceptance-20260818.md`.

## Mail Room and correspondence

Fresh previously accepted Mail AI behavior remains:

- `mail.status.read`;
- `mail.draft.prepare`;
- prepared-not-sent semantics;
- no send/mutation authority.

The source audit remains decisive:

- `server/mail_threading.py` provides explicit correlation metadata but no body store;
- `server/inbound_mail_hub.py` is disabled-by-default routing/audit logic and is not correspondence storage;
- `config/messaging/inbound-mail-hub.json` keeps raw-message, attachment-byte, and body-preview persistence disabled;
- provider inventory does not prove the canonical provider-side mailboxes are provisioned.

Phase 27 merged `server/mail_correspondence_store.py`, a private bounded SQLite message/thread persistence foundation. It preserves canonical Message-ID, provider message/thread IDs, explicit thread/reply relationships, immutable per-record source/authority provenance, bounded bodies/results, and marks all returned bodies untrusted with `mutation_authorized=false` and `send_authorized=false`. Synthetic validation is in `tests/validate_mail_correspondence_store.py`.

PR review found and fixed a provenance bug before merge: a synthetic record can no longer be relabeled authoritative merely by reopening the database with a differently configured reader. The authority flag is persisted per record and covered by regression validation.

This local store does **not** itself make correspondence authoritative. `mail.correspondence.read` remains intentionally disabled until a reviewed native source is explicitly selected and connected: either a trusted local MTA/Mail Room intake or an explicitly authorized native mailbox/provider connector with stable native IDs and real message bodies. Outbound audit metadata must never be substituted for correspondence.

## Communications Relay and workspace

Earlier fresh acceptance remains authoritative for the bounded metadata plane:

- `edge1-comms-relay.service` is the authoritative native Relay/NNTP source;
- persistent workspace is loopback-only at `127.0.0.1:8095`;
- live attached snapshot contained 168 canonical events at acceptance;
- content is marked untrusted and mutation is false;
- POST remained HTTP 405;
- the 15-minute snapshot refresh timer is enabled;
- no public/reverse-proxy exposure is authorized.

## Voice/SIP

Phase 19 passed fresh bounded read-only functional acceptance: Asterisk, Kamailio, analytics and console stayed active; runtime source hashes matched the reviewed repository; analytics remained loopback-only on `127.0.0.1:8099`; aggregate endpoints/privacy validation passed; POST returned HTTP 405; and no calls, DTMF, routes, carrier configuration, database mutation, credentials, service restart, or runtime mutation occurred.

Operational-health freshness is separate. The API-reported `critical` / `sip: degraded` state came from repository snapshot `data/registry/interconnect/status/peer-status.json` last checked 2026-07-20, not from a fresh live carrier/interconnect probe. Therefore:

- `voice_sip.live_acceptance = runtime_ready` for the bounded read-only surface;
- `voice_sip.edge1_runtime = unknown` for current interconnect health.

Do not use production calls or unauthorized route/carrier changes merely to obtain health evidence.

## Private AI

Fresh accepted BigBird state remains `0.3.4-alpha.3`, read-only, loopback-only at `127.0.0.1:8787`, with explicit scope checks, missing-scope fail-closed behavior, Messaging conversation reads and local draft preparation. Messaging control remains disabled. Retrieved communications remain untrusted data and cannot grant scopes or tool authority.

## Validation and evidence

Exact-head Phase 27 CI on `ec8f069c39947cfdb944e7782fef72b71a274638` passed before merge:

- WW.CX Messaging Gateway — run `32194754869`;
- Validate repository — run `32194754894`;
- Edge1 Operator Validation — run `32194754898`.

Current durable records:

- `config/communications/readiness-matrix-v1.json`;
- `.agent/unified-communications-validation-20260818.md` — prior live acceptance record;
- `.agent/unified-communications-validation-phase27-20260818.md` — Phase 27 repository/CI/runtime-separation record;
- `.agent/unified-communications-backlog-20260818.md`;
- `docs/communications/unified-communications-phase27-runtime-acceptance-20260818.md`;
- `docs/handoff/unified-communications-phase27-20260818.md`;
- earlier live acceptance records under `docs/communications/`.

Repository CI and live-host evidence are separate. Green GitHub checks never substitute for authenticated Edge1 runtime acceptance.

## Remaining global blockers

1. **MMS live security runtime:** authenticate to Edge1; inspect the actual service identity/resources/scanner state; establish or approve a trusted local scanner; create/verify the private quarantine root; run synthetic clean/EICAR/unavailable/timeout/error/digest/integrity/restart tests; verify permissions, listeners, adjacent services, and rollback. No carrier traffic.
2. **Mail authoritative correspondence source:** explicitly authorize and connect one native mailbox/MTA source to the private store/read adapter, preserve native IDs/provenance, then perform bounded live read-only acceptance. Until then `mail.correspondence.read` stays blocked.
3. **Voice/SIP operational health:** optional separate read-only freshness follow-up; not a missing functional-acceptance gate.

`fresh_edge1_runtime_verified` must remain `false` until the intended safe-scope MMS runtime is genuinely accepted and the Mail correspondence-source gap is genuinely resolved or explicitly closed with evidence.

## Non-negotiable production boundaries

Without separate explicit authorization, do not originate production calls, send live SMS/MMS, send live email, alter emergency calling, change carrier routes/trunks/dialplans, perform number porting or STIR/SHAKEN actions, modify firewall/DNS/certificates/authentication policy, rotate/disclose credentials, expose new public management listeners, release quarantine, perform destructive/irreversible deletion, or enter financial/contractual/legal/regulatory commitments.
