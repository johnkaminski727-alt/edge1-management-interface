# AVA Reconciliation Plan — 2026-10-02

## Purpose

Reconcile the useful AVA runtime work from `agent/ava-runtime-commissioning-20260930`
into the current authenticated Control Center lineage without regressing the accepted
Phase 3 browser, authentication, navigation, deployment or Contacts experience.

This plan replaces the older assumption that the AVA runtime commissioning branch
should become the whole deployed Edge1 interface.

## Current authoritative split

### Control Center / browser / authentication lineage

Authoritative base: `phase-3m-ava-ingress-policy-test-fix-20261001` and descendants.

This lineage owns:

- authenticated `/edge1-ops/*` browser namespace;
- current light/shared Operator Shell;
- authenticated specialist module ingress;
- Contacts & Relationships at `/edge1-ops/contacts/`;
- AVA candidate ingress at `/edge1-ops/ava/`;
- release-worktree-aware Control Center publication;
- transparent Control Center navigation;
- canonical navigation order with Contacts first and AVA second.

Do not publish full Control Center assets from
`agent/ava-runtime-commissioning-20260930`.

### AVA runtime donor lineage

Donor branch: `agent/ava-runtime-commissioning-20260930`.

This branch remains valuable for runtime/backend work, including:

- rebuilt dependency-light AVA / Big Bird gateway on loopback;
- bounded AVA agent controller;
- Private Library integration;
- signed browser-worker / gateway path;
- Contacts-aware source/capability integration;
- fail-closed behavior when model/provider credentials are unavailable;
- runtime commissioning helpers and regression coverage.

The branch is a donor/source branch, not the browser/UI release authority.

## Known divergence

The two lines have diverged substantially from their common ancestor. Reconciliation
must therefore be selective. Do not merge either branch wholesale into the other.

Required classification for donor-side changes:

1. **Carry forward** — runtime/backend functionality still required.
2. **Already superseded** — equivalent or better behavior exists in Phase 3.
3. **Conflict / adapt** — still useful but must be changed to match current auth,
   routes, Contacts contracts, or deployment model.
4. **Retire** — obsolete assumptions, duplicated UI, old deployment paths, or
   no-longer-valid scaffolding.

## Non-negotiable preserved state

Reconciliation must not regress:

- current authenticated Control Center shell and styling;
- working authenticated Contacts route;
- current navigation order;
- session-cookie and server-side authorization boundaries;
- candidate-vs-live distinction for AVA;
- release-root / reviewed-worktree deployment behavior;
- current live services or unrelated in-progress Contacts CRUD work;
- fail-closed AVA authority gates.

## Work phases

### Phase 3O.1 — donor inventory

Inventory all AVA-runtime-side commits/files not present in the Phase 3M lineage.
Group them by subsystem:

- gateway / model path;
- browser worker and signed queue;
- AVA agent controller;
- Private Library integration;
- Contacts integration;
- office-manager / call archive dependencies;
- deployment / commissioning helpers;
- tests and documentation;
- UI or shell changes.

No production mutation is authorized by this inventory phase.

### Phase 3O.2 — supersession matrix

For every donor subsystem, record:

- current Phase 3 equivalent, if any;
- donor revision/source;
- disposition: carry / superseded / adapt / retire;
- required tests;
- live acceptance requirement;
- rollback boundary.

Any donor UI/shell change defaults to **superseded** unless proven otherwise.

### Phase 3O.3 — runtime integration slices

Carry forward runtime work in small reviewable slices onto this Phase 3O branch.

Preferred order:

1. gateway/runtime primitives;
2. browser-worker and signed queue integration;
3. AVA controller;
4. Private Library adapter;
5. Contacts adapter against the current Contacts contract;
6. commissioning/install helpers adapted to reviewed release roots;
7. regression tests and operational documentation.

Each slice must avoid unrelated UI publication.

### Phase 3O.4 — AVA authenticated browser acceptance

Only after runtime reconciliation:

- verify `/edge1-ops/ava/` through the current authenticated ingress;
- verify AVA read API through the current server-side boundary;
- verify no credentials/HMAC material reach the browser;
- verify direct unauthenticated access fails correctly;
- verify restricted/confirmation/raw-shell gates still fail closed;
- verify current Contacts page and Control Center navigation are unchanged.

Only then consider promoting AVA from candidate/upcoming to accepted browser navigation.

### Phase 3O.5 — closeout

After successful acceptance:

- record exact accepted commits;
- merge the reconciliation line into the current Phase 3 lineage;
- mark the old AVA runtime branch/PR as historical donor work;
- remove any instruction that suggests deploying the old branch wholesale;
- preserve rollback/evidence records.

## Immediate implementation rules

- Do not reset or repurpose the dirty live Edge1 management checkout.
- Do not use the old AVA runtime checkout as a full Control Center publisher source.
- Use reviewed release worktrees for deployable artifacts.
- Do not install missing development packages on the production host merely to run
  repository tests; use CI or isolated release/test worktrees instead.
- Preserve live navigation and shell assets until an exact reviewed descendant is
  ready to replace them.
- Treat local uncommitted Contacts CRUD work as a separate preservation/reconciliation
  concern; never overwrite it while integrating AVA.

## Current next action

Begin Phase 3O.1 donor inventory and create the supersession matrix before copying
runtime code. Backend AVA functionality may then be integrated slice-by-slice while
the current Control Center remains untouched.
