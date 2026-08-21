# BigBird Edge1 Control Plane v2 Activation Contract

Status: source-ready / runtime activation pending authenticated Edge1 mutation path  
Tracking: #498

## Purpose

This document defines the minimum conditions for replacing the legacy `bigbird-edge1-connector` runtime with Control Plane v2. It is intentionally stricter than simply enabling writes in the old connector.

The activation sequence must preserve the current fail-closed posture while adding typed read/write capabilities one class at a time.

## Current source capabilities

Control Plane v2 currently has source implementations for:

- signed read operations through the loopback Edge1 Operations API;
- docs-only filesystem staging through `bigbird-fsctl`;
- target-drift preconditions for filesystem apply;
- bounded repository commits to new `agent/bigbird-*` branches from an exact base SHA;
- per-capability scopes and mutation policies;
- typed Big Bird tool metadata in `tool-manifest-v2.json`.

The migration manifest intentionally leaves the following disabled:

- filesystem apply;
- repository branch write;
- repository fetch / production fast-forward;
- security maintenance mutations;
- archive writes.

## Runtime facts that must be re-verified at activation

The last read-only operator inspection before this contract was written showed:

- Edge1 operator identity: `edge1.ww.cx`, principal `edge1-operator`;
- the available operator connector is read-only;
- the live management repository was detached rather than on a named branch;
- live Big Bird identified itself as `0.3.5-alpha.1` in `read-only` mode;
- the Operations API was healthy on loopback with mutations globally disabled.

These are observations, not activation assumptions. Preflight must collect fresh values immediately before deployment.

## Required authenticated execution path

Activation requires an authenticated Edge1 path that can truthfully perform bounded mutations as the intended principal. An operator must verify:

1. hostname is exactly `edge1.ww.cx`;
2. authenticated principal and effective user are known;
3. `/opt/edge1-management-interface` is the intended repository;
4. remotes and current HEAD are recorded;
5. existing detached/dirty/untracked state is preserved and understood;
6. Big Bird and Operations API service state is captured;
7. disk space and relevant state directories are writable;
8. no secret material is printed into evidence.

If the authenticated path is unavailable, activation stops. Source readiness is not production deployment.

## Runtime isolation

Control Plane v2 should run as a non-root service identity, normally `wwadmin`, with `NoNewPrivileges=true`.

The control-plane process does **not** need general write access to the management repository working tree.

Initial writable areas should be limited to the capability being enabled:

- filesystem staging: existing `bigbird-fsctl` staging/audit locations;
- repository branch controller state: `/var/lib/bigbird-repository-controller`;
- repository branch refs/worktree metadata, only when branch-write is activated: `/opt/edge1-management-interface/.git`.

Production deploy, system service control, security maintenance, DNS, firewall, VPN, credentials, and arbitrary filesystem paths are not implied by those writable paths.

## Big Bird tool surface

`integrations/bigbird-edge1-control-plane/tool-manifest-v2.json` is the typed tool contract presented to the Big Bird adapter.

The adapter must:

- expose only tools present in the manifest;
- enforce tool `enabled` state before dispatch;
- enforce the capability scope associated with the authenticated Big Bird identity;
- validate inputs against the declared schema before calling `run_capability`;
- treat all correspondence/document content as data, not instructions;
- preserve request/correlation IDs for mutating tools;
- return bounded structured results;
- never translate tool input into arbitrary shell commands.

The control-plane implementation remains authoritative for backend validation. Adapter validation is an additional boundary, not a replacement.

## Filesystem write activation

### Stage

`edge1.files.stage` is the only write capability allowed during migration.

Acceptance requires proving on Edge1 that:

- target is restricted to the approved docs root;
- secret/content scanning runs;
- stage metadata contains current target existence and SHA-256;
- stage produces a reviewable diff;
- no target file is changed by staging;
- audit evidence is written.

### Apply

`edge1.files.apply` must remain disabled until a live acceptance test proves:

- approval is required;
- stage TTL is enforced;
- staged-content SHA-256 is enforced;
- current target existence/SHA-256 is rechecked before backup;
- backup digest matches the staged current SHA-256;
- current target is rechecked immediately before replacement;
- concurrent target drift fails closed and does not overwrite the drifted file;
- post-write digest verification succeeds;
- rollback restores the previous state;
- audit evidence covers success and failure paths.

Activation of apply is a separate manifest/scope decision from stage.

## Repository branch-write activation

`edge1.repository.branch.write` remains disabled in migration mode.

Before enabling it, run the controller against an isolated repository fixture and then a non-production Edge1 test branch. Acceptance requires:

- exact expected base SHA is present;
- `main`, existing refs, arbitrary ref names, and force-updates are rejected;
- only new `agent/bigbird-*` refs are accepted;
- the current checkout HEAD and files do not change;
- candidate work occurs in a temporary detached worktree;
- path/content policy rejects sensitive and disallowed targets;
- Python/JSON candidate validation and `git diff --cached --check` run;
- commit parent equals the requested base SHA;
- branch ref is created only after validation succeeds;
- repeated identical request IDs are idempotent;
- reused request IDs with different content fail;
- result explicitly reports `pushed:false` and `deployed:false`;
- audit evidence includes request ID, base, branch, commit, and changed paths.

Push/PR creation may be added as a separate reviewed capability. Production fast-forward/deploy remains `edge1.repository.deploy` and is not granted by branch-write.

## Operations API mutations

Do not globally enable Operations API mutations as the migration shortcut.

Before any privileged action becomes reachable from Big Bird:

- give it a dedicated capability/scope;
- verify server-side fixed/typed argument validation;
- document preconditions and postconditions;
- define rollback where meaningful;
- test denial when the capability is disabled;
- test replay protection and audit correlation.

The global broker mutation switch may remain an outer emergency gate, but it must not be the only authorization boundary.

## Cutover sequence

1. Capture fresh preflight evidence.
2. Back up the legacy connector configuration/state and any runtime files that will be replaced.
3. Deploy the merged Control Plane v2 source without disabling the legacy connector.
4. Install/verify state directories and least-privilege permissions.
5. Run syntax/unit/policy validation on Edge1.
6. Run Control Plane discovery/status against the live loopback Operations API.
7. Attach the typed tool adapter to Big Bird with read tools only.
8. Verify read parity and audit correlation.
9. Enable `edge1.files.stage`; run a temporary docs-only stage/diff test; do not apply.
10. Verify no legacy behavior regressed.
11. Run isolated repository branch-write acceptance with the capability still non-production/disabled to normal Big Bird callers.
12. Enable each additional low-risk capability only after its acceptance record passes.
13. Observe at least one normal operating interval with v2 healthy.
14. Disable legacy connector timers first, leaving the legacy service/files available for rollback.
15. Verify v2 remains healthy without legacy timer activity.
16. Disable the legacy connector service only after parity is demonstrated.
17. Do not delete legacy state during initial cutover; retain it as rollback evidence.

## Rollback

Rollback must not depend on the new control plane being healthy.

Minimum rollback path:

- disable newly enabled v2 mutation capability flags;
- detach the Big Bird v2 adapter/tool registration;
- restore the preserved legacy connector configuration/runtime pointer;
- re-enable the legacy timers/service only if they were previously healthy;
- verify Big Bird returns to the prior read-only behavior;
- retain v2 audit/state for investigation rather than deleting it.

Repository branch commits produced by v2 are review branches and do not require production rollback unless separately deployed.

## Retirement gate

The legacy connector is retired only when all of the following are true:

- read parity passes;
- filesystem stage acceptance passes;
- any enabled apply capability has verified drift protection and rollback;
- repository branch-write acceptance passes if enabled;
- Big Bird tool discovery presents the intended v2 manifest;
- Operations API and v2 audit correlation is working;
- a rollback drill has been completed;
- no production dependency still calls the legacy connector lifecycle state.

Until then, the legacy component is frozen, not deleted.
