# AVA Phase 3O — Edge1 detached release preflight

Date: 2026-10-02

This runbook performs the first host-side validation of the reconciled AVA runtime
without modifying the dirty/live management checkout and without starting, stopping,
restarting, enabling, or replacing any AVA service.

## Preconditions

- PR #631 CI is green at the exact reviewed commit.
- Use the exact reviewed 40-character commit SHA; do not substitute a branch name for
  the preflight gate.
- The existing `/opt/edge1-management-interface` checkout is not reset, cleaned,
  switched, or reused for release testing.
- No full Control Center publisher is invoked.

## Create an isolated detached worktree

Run as the normal Edge1 operator:

```sh
# TARGET: edge1
set -euo pipefail

cd /opt/edge1-management-interface
git fetch origin phase-3o-ava-reconciliation-20261002

REVIEWED_SHA="<REVIEWED_SHA>"
RELEASE_ROOT="/opt/edge1-release-worktrees/ava-phase3o-${REVIEWED_SHA}"

sudo install -d -m 0755 -o wwadmin -g wwadmin /opt/edge1-release-worktrees

git worktree add --detach "$RELEASE_ROOT" "$REVIEWED_SHA"

git -C "$RELEASE_ROOT" rev-parse HEAD
git -C "$RELEASE_ROOT" status --short --branch
```

Expected state:

- HEAD exactly equals `REVIEWED_SHA`;
- worktree is detached;
- working tree is clean.

## Run the read-only preflight

```sh
# TARGET: edge1
set -euo pipefail

REVIEWED_SHA="<REVIEWED_SHA>"
RELEASE_ROOT="/opt/edge1-release-worktrees/ava-phase3o-${REVIEWED_SHA}"

"$RELEASE_ROOT/deploy/preflight-ava-phase3o-release.sh" \
  --expected-commit="$REVIEWED_SHA"
```

The preflight performs:

- exact-commit / detached / clean-worktree validation;
- required-source inventory;
- Python compilation;
- installer shell syntax checks;
- systemd static verification when available;
- dry-run execution of all three commissioning helpers;
- focused unittest coverage;
- read-only inspection of relevant live service state, immutable-runtime pointers, and
  loopback listeners.

It does **not**:

- call installer `--apply`;
- start/restart/enable/disable a service;
- change runtime symlinks;
- write credentials;
- publish Control Center assets;
- change nginx/auth/browser routes;
- promote AVA in the navigation registry.

## Stop conditions

Stop before any commissioning apply if any of the following occur:

- commit mismatch;
- dirty or non-detached release worktree;
- compile/test/static-unit failure;
- installer dry-run failure;
- unexpected live runtime pointer type;
- unexpected loss of an existing AVA/worker service or listener;
- evidence that the preflight would touch the active Control Center or Contacts UI.

## After a successful preflight

A successful preflight is evidence only. It does not authorize live activation.

The next separately reviewed stage is:

1. Private Library database commissioning, without starting services;
2. AVA gateway immutable release install, initially without `--start`;
3. browser-worker immutable release install, initially without `--start`;
4. compare installed files/runtime pointers against the prior live state;
5. only then consider an attended start/restart with rollback armed.

Keep AVA browser-route promotion separate until the runtime path and authenticated
`/edge1-ops/ava/` acceptance both pass.
