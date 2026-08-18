# WW.CX Unified Communications — Phase 27 Handoff

Date: 2026-08-18
Repository: `johnkaminski727-alt/edge1-management-interface`
Base main at Phase 27 branch creation: `967096132bc5f998d68893ff43c81ffc3f37e2b5`
Implementation branch: `agent/unified-communications-phase27-20260818`
Reviewed exact head: `ec8f069c39947cfdb944e7782fef72b71a274638`
PR: #424 — merged
Merge SHA: `d01a2620c8d252260391cc9a2f86ec32938c146c`

## Current result

Phase 27 closes the remaining **repository implementation** gaps for a concrete trusted local MMS scanner adapter and a private Mail correspondence-store foundation. PR #424 merged after all exact-head required CI was green. This does not claim live Edge1 deployment or an authoritative production Mail source.

### MMS

Repository-ready and merged:

- existing content-addressed quarantine storage and fail-closed state machine;
- fixed-path `/usr/bin/clamscan` adapter behind `TrustedMediaScanner`;
- bounded subprocess timeout/error handling;
- no arbitrary command hook, cloud scan, public listener, or automatic release;
- local-only synthetic clean/EICAR/restart acceptance script;
- unit tests for fixed command construction, clean/malicious verdicts, unavailable/error/timeout behavior, and unsafe blob-path rejection.

Still requiring authenticated Edge1 acceptance:

- confirm host/principal and actual Messaging service identity;
- confirm resource state and whether ClamAV/signatures already exist;
- if absent, determine whether package installation is authorized and resource-safe;
- create/verify the dedicated private root outside any web document root;
- run local synthetic clean/EICAR/failure/restart acceptance;
- verify private ownership/modes, no new public listener, adjacent service health, rollback, and no release path.

### Mail

Repository-ready and merged:

- private SQLite persisted correspondence store;
- canonical native Message-ID preservation;
- provider message/thread ID preservation;
- explicit thread ID and reply/reference relationships;
- bounded message/thread reads;
- immutable per-record source/authority provenance;
- untrusted body treatment;
- no send/routing/mutation authority;
- synthetic local validation including a regression test proving a later reader cannot relabel synthetic records authoritative.

Still blocked for `mail.correspondence.read`:

- no authoritative native provider/MTA body/thread source is currently proven or connected;
- current inbound hub remains disabled and does not persist message bodies;
- provider inventory does not prove the canonical provider mailboxes are provisioned.

The smallest external resolution is to explicitly authorize and connect one native source: either the reviewed local MTA/Mail Room intake or an authorized native mailbox/provider connector that supplies stable native IDs and bodies. Until then, do not advertise `mail.correspondence.read` as available.

## GitHub validation and merge

Exact-head CI on `ec8f069c39947cfdb944e7782fef72b71a274638`:

- WW.CX Messaging Gateway — run `32194754869` — **success**;
- Validate repository — run `32194754894` — **success**;
- Edge1 Operator Validation — run `32194754898` — **success**.

No inline review threads remained. PR #424 merged to `main` as `d01a2620c8d252260391cc9a2f86ec32938c146c`.

## Edge1 deployment / live acceptance

No authenticated Edge1 execution path was exposed to this session. The available container had no SSH agent or SSH identity, the Edge1 Live Shell connector was unavailable, and no installable Edge1 plugin was found. Therefore Phase 27 live deployment and acceptance were not attempted or simulated.

Use `docs/communications/unified-communications-phase27-runtime-acceptance-20260818.md` when an approved authenticated Edge1 path is available.

## Readiness dimensions

- repository implementation: **repository-ready / merged** for MMS trusted-scanner adapter and Mail persisted-store foundation;
- local/repository tests: **implemented**; GitHub exact-head validation green;
- GitHub CI: **green** for all Phase 27 required workflows;
- merge state: **merged** as `d01a2620c8d252260391cc9a2f86ec32938c146c`;
- Edge1 deployment: **not performed**, blocked by missing authenticated execution connector in this session;
- live functional acceptance: **not performed for Phase 27**;
- security/privacy acceptance: repository invariants green; live ownership/permissions/listener checks pending;
- external/provider readiness: unchanged/unknown;
- production authorization: blocked/unchanged.

`fresh_edge1_runtime_verified` remains `false`.

## Safety state

Unchanged prohibitions:

- no live SMS/MMS or carrier traffic;
- no live email send;
- no call origination;
- no emergency/SIP/carrier route changes;
- no DNS/firewall/certificate/authentication changes;
- no credential disclosure/rotation;
- no quarantine release;
- no destructive deletion;
- no financial/legal/regulatory commitments.

## Recovery point

Continue from this handoff together with:

- `.agent/unified-communications.md`;
- `.agent/unified-communications-validation-phase27-20260818.md`;
- `.agent/unified-communications-backlog-20260818.md`;
- `config/communications/readiness-matrix-v1.json`;
- `docs/communications/unified-communications-phase27-runtime-acceptance-20260818.md`.

Do not set `fresh_edge1_runtime_verified=true` until the live safe-scope MMS runtime is genuinely accepted and the Mail correspondence source gap is genuinely resolved or explicitly closed with evidence.
