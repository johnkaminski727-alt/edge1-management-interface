# Edge1 Operations API Repository-Root Stability

Status: source hardening for an observed read-only repository-identity discrepancy. This document does not claim the live cause has been proven and does not authorize a service restart or repository mutation.

## Observed evidence — 2026-08-22

During Cookie Monster live-state preflight, two read-only views of the Edge1 management repository disagreed within the same inspection window:

- the bounded Operations API `repository.status` / `repository.head` actions reported a detached checkout at `d326d4546abefa695a293266342a5c1075f010e2`;
- the deterministic Edge1 snapshot resolved `/opt/edge1-management-interface` and reported branch `main` at `20b3f6c2a5a3da6484b433f6f171c3c713ef920e` with `## main...origin/main`;
- the Operations API `config.digest` action and the snapshot agreed on the allowlist and Operations API service digests, but disagreed on the repository-controlled `deploy/edge1-operator/edge1-operator-mcp.service` digest.

The inspection was read-only. The Operations API itself was healthy enough to answer requests and reported mutations disabled.

## Why this matters

`server/edge1_operations_api.py` resolves `EDGE1_OPS_ROOT` at process start. This is normally harmless for a stable directory. If the configured path is a deployment symlink and its target changes while the service remains running, the process can remain bound to the repository generation it resolved at startup while another fresh process resolves the logical path to the new generation.

That mechanism is **consistent with** the observed disagreement, but the read-only connector cannot prove that a symlink/release switch is the actual live cause. Other deployment-state differences must remain possible until an authenticated host operator inspects the live path/unit environment directly.

Regardless of cause, contradictory repository identity is not an acceptable basis for a write-capable control plane.

## Source hardening

The Operations API now keeps both:

- the configured logical repository path, without resolving its deployment target; and
- the repository target resolved at service startup.

Before loading the allowlist or dispatching any action, it resolves the logical path again. If the target no longer matches the startup target, it fails closed with a service-restart-required error.

Consequences:

- `/healthz` becomes HTTP 503 and reports `repository_root_stable: false` when drift is detected;
- authenticated action listing returns HTTP 503 instead of advertising policy from an ambiguous repository generation;
- action dispatch fails before execution when root identity has changed;
- mutation-disabled behavior remains unchanged;
- no automatic restart, symlink rewrite, repository pull, branch change, or deployment repair is introduced.

## Deployment rule

Any deployment workflow that changes the target of the configured Edge1 Operations API repository root must restart the Operations API as part of the reviewed deployment transaction, then verify:

1. `/healthz` is healthy and `repository_root_stable` is true;
2. `repository.head` agrees with the intended deployed repository identity;
3. an independently collected snapshot reports the same repository head/branch;
4. repository-controlled configuration digests agree across both observation paths;
5. Operations API mutations remain disabled unless a separate authorization explicitly changes that policy.

If those checks disagree, stop. Do not use repository mutation actions to try to repair the repository from the ambiguous API process.

## Validation

`tests/test_edge1_operations_api.py` covers:

- ordinary safe action execution/audit;
- mutation-disabled policy;
- unknown-action and cwd-escape refusal;
- stable repository root acceptance;
- configured symlink target change refusal;
- configured repository root disappearance refusal.

The new tests are source-level controls. They do not prove the current live Edge1 process has been restarted onto the intended repository generation.
