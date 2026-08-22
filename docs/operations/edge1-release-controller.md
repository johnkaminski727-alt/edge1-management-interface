# WW.CX Edge1 Durable Release Controller

Status: repository implementation. Live installation/promotion is a separate attended acceptance step.

## Problem being solved

The Edge1 management checkout was observed through two read-only paths at two different repository generations during the same inspection window. A long-running Operations API process reported an older detached generation while a fresh host snapshot resolved `/opt/edge1-management-interface` to a newer generation. PR #525 made the Operations API fail closed if its configured root changes underneath it, but fail-closed detection alone is not a deployment mechanism.

The durable solution is to stop using one mutable checkout as both **source workspace** and **running control-plane code**.

## Permanent model

```text
GitHub main
    |
    v
/opt/edge1-management-source          mutable source checkout, branch main
    |
    | exact reviewed 40-char commit
    v
/opt/edge1-runtime/releases/<sha>     immutable/detached runtime release
    |
    +--> /opt/edge1-runtime/current   atomic active pointer
    |
    +--> /opt/edge1-runtime/previous  exact rollback pointer
              |
              +--> edge1-operations-api.service
              +--> edge1-operator-mcp.service
```

The legacy `/opt/edge1-management-interface` checkout remains available for bootstrap/source provenance while the controller is introduced. It is no longer intended to be the permanent runtime code root for the two managed control-plane services after first successful promotion.

## Invariants

- A merge to `main` does **not** automatically deploy to Edge1.
- Promotion always names one exact 40-character Git commit SHA.
- The target must already be reachable from the dedicated source checkout's local `origin/main` ref.
- Runtime releases are separate local clones, detached at the exact target commit.
- Only one `current` pointer defines the running control-plane generation.
- The exact former current release becomes `previous` before a switch.
- Only `edge1-operations-api.service` and `edge1-operator-mcp.service` are managed initially.
- Operations API mutations remain disabled.
- Ports 8097 and 8102 must remain loopback-only.
- A failed post-switch health check triggers automatic restoration of the prior pointer/drop-ins and restarts the prior generation.
- Periodic status is read-only. It detects and displays drift; it never promotes code.
- No arbitrary command, path, branch, URL or service name is accepted by the release action.

## Components

### `server/edge1_release_controller.py`

Persistent controller with four operator verbs:

```text
status
prepare <exact-sha>
promote <exact-sha>
rollback-last
```

`prepare` and `promote` require root. `status` is read-only. `rollback-last` uses the exact controller-recorded previous release rather than accepting a user-supplied rollback path.

### Dedicated source checkout

`deploy/install_edge1_release_controller.py --apply` creates `/opt/edge1-management-source` when absent by cloning the existing management repository locally. It then rebinds the new checkout's `origin` to the legacy repository's canonical remote when that remote can be copied safely without embedded HTTP credentials.

The dedicated source checkout must remain:

- branch `main`;
- clean;
- owned by the existing `wwadmin` source-maintenance identity;
- separate from `/opt/edge1-runtime`.

### Runtime releases

Prepared releases live under:

```text
/opt/edge1-runtime/releases/<40-char-sha>
```

The controller creates each release by local clone with `--no-hardlinks`, checks out the exact commit detached, verifies a clean worktree, and confirms required control-plane/release-controller source is present.

The use of `--no-hardlinks` ensures a runtime release has its own Git object files rather than depending on source-repository hardlinks for continued readability.

### Systemd release root

The controller transactionally manages drop-ins for:

```text
/etc/systemd/system/edge1-operations-api.service.d/20-edge1-release-root.conf
/etc/systemd/system/edge1-operator-mcp.service.d/20-edge1-release-root.conf
```

Both services get `/opt/edge1-runtime/current` as their working code root. The Operations API additionally receives:

```text
EDGE1_OPS_ROOT=/opt/edge1-runtime/current
```

That intentionally works with the PR #525 root-stability guard: after a reviewed pointer switch the API is restarted, resolves the new target at process start, and then fails closed if the pointer is changed again without another reviewed service transaction.

## Promotion transaction

A promotion performs this bounded sequence:

1. Validate exact target syntax.
2. Require a clean dedicated source checkout on `main`.
3. Require the target to be present and reachable from local `origin/main`.
4. Prepare/reuse the exact detached runtime release.
5. Create a timestamped transaction directory under `/var/backups`.
6. Hash/back up any existing managed systemd drop-ins.
7. Install the target release-root drop-ins.
8. Record the exact old `current` and `previous` release identities.
9. Move the old current release to the `previous` pointer.
10. Atomically replace the `current` pointer with the target release.
11. Run `systemctl daemon-reload`.
12. Restart only the two fixed managed services.
13. Verify the current pointer still equals the target.
14. Verify both services are active.
15. Verify Operations API health is `ok`.
16. Verify `repository_root_stable=true`.
17. Verify `mutations_enabled=false`.
18. Verify ports 8097 and 8102 are present and loopback-only.
19. Refresh `/usr/local/libexec/edge1-release-controller` from the successfully promoted release.
20. Persist the successful transaction and current/previous state.

If any post-switch step fails, the controller restores the former pointers and backed-up drop-ins, reloads systemd, restarts the former generation and verifies the former release again. The failure record states whether automatic rollback succeeded.

## Persistent status and cockpit

The installer adds:

```text
edge1-release-controller-status.service
edge1-release-controller-status.timer
```

The timer runs every five minutes and survives reboot via `Persistent=true`. It only computes status and writes:

```text
/var/lib/edge1-release-controller/status.json
/var/www/edge1-status/release-manager/status.json
```

The human-facing page at candidate route `/edge1-status/release-manager/` shows:

- current runtime commit;
- previous rollback commit;
- source checkout head/branch/dirty state;
- whether source differs from runtime;
- managed service state;
- Operations API root-stability state;
- mutation-disabled state;
- loopback listener state;
- last transaction outcome.

The page is read-only and explicitly displays **Automatic promotion: OFF**. Repository registration remains `staged_disabled` until real browser/runtime acceptance is completed.

## Attended live-shell action

The Edge1 live-shell sidecar exposes one additional named tool:

```text
edge1_release(action=status|reconcile|rollback_last)
```

`status` is read-only.

`reconcile` is unavailable unless the operator environment explicitly sets:

```text
EDGE1_ALLOW_RELEASES=1
EDGE1_RELEASE_TARGET_SHA=<exact 40-char commit>
```

It does not accept the target from the caller. The target is pinned in the operator environment.

For first bootstrap, `reconcile`:

1. fetches the existing legacy repository's `origin`;
2. verifies the pinned target exists and is reachable from `origin/main`;
3. creates a temporary detached worktree at that exact target;
4. runs the target's backup-first release-controller installer;
5. removes the bootstrap worktree;
6. fetches the new dedicated source checkout;
7. verifies it is clean `main` and the same target is reachable;
8. prepares and promotes the exact target;
9. writes/publishes the persistent status snapshot.

`rollback_last` is also gated by `EDGE1_ALLOW_RELEASES=1` and accepts no path or target.

Raw shell remains a separate disabled-by-default capability and is not required by the release workflow.

## Installer and rollback

Read-only preflight:

```bash
python3 deploy/install_edge1_release_controller.py
```

Reviewed install:

```bash
sudo python3 deploy/install_edge1_release_controller.py --apply
```

The installer backs up the controller executable, status service/timer and release-manager page before mutation. Installation creates the durable source/status foundations only; it does not switch `current`, install the runtime service drop-ins or restart the managed control plane.

Installer rollback uses the exact backup directory returned by apply:

```bash
sudo python3 deploy/install_edge1_release_controller.py \
  --rollback /var/backups/edge1-release-controller-install-<exact-stamp>
```

The dedicated source clone is intentionally preserved by installer rollback because deleting a newly-created Git source tree during a config rollback is an unnecessarily destructive operation. Runtime promotion has its own exact previous-release rollback.

## First live acceptance gate

Do not mark the Release Manager navigation entry `accepted_live` until an attended first reconciliation has proven all of the following after the transaction:

- the exact approved target is under `/opt/edge1-runtime/releases/<sha>`;
- `/opt/edge1-runtime/current` resolves to that exact release;
- `/opt/edge1-runtime/previous` records the prior generation when one existed;
- both managed services are active;
- Operations API `/healthz` reports `status=ok` and `repository_root_stable=true`;
- Operations API still reports `mutations_enabled=false`;
- ports 8097 and 8102 remain loopback-only;
- an independent Edge1 snapshot and the runtime status page agree on the intended control-plane state;
- `/edge1-status/release-manager/` renders the persistent status snapshot;
- rollback/evidence artifacts are retained.

Only after those observations should the navigation registry be promoted from `staged_disabled` to `accepted_live` in a separate reviewed change.

## What this intentionally does not do

- no deploy-on-every-merge automation;
- no branch-name deployment;
- no arbitrary shell deployment API;
- no arbitrary systemd service input;
- no DNS/firewall/certificate/authentication changes;
- no public listener changes;
- no Cookie Monster archive authority changes;
- no canonical archive selection;
- no automatic deletion of old releases.

Old-release retention can be added later as a bounded garbage-collection policy only after at least the current and previous releases plus active rollback/evidence dependencies are protected.

## Provenance

- PR #525 — Operations API repository-root drift fails closed.
- PR #529 — bounded, exact-SHA Cookie Monster live activation sidecar foundation.
- Issue #530 — durable Edge1 runtime release controller objective.
