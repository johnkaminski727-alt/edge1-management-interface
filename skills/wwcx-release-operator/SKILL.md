---
name: wwcx-release-operator
description: Plan, execute, and verify WW.CX releases to Edge1, Business159, or both through existing bounded deployment/operator mechanisms. Use for release preflight, source/branch/hash verification, backup/checkpoint, deploy candidate, syntax/static checks, functional smoke tests, activation, post-release health, evidence capture, rollback, and coordinated cross-host release verification.
---

# WW.CX Release Operator

Use existing host-specific deployment mechanisms; do not create a parallel deploy system merely for uniformity.

Required lifecycle:

`identify target -> verify source/branch -> preflight -> verify artifacts/hashes -> preserve state -> backup/checkpoint -> deploy candidate -> syntax/static validation -> functional smoke test -> activate -> verify process/application/HTTP health -> capture evidence -> finalize or roll back`

## Business159

Use `business159_deploy`. Dry-run first. Apply only when deployment is authorized, `BUSINESS159_ALLOW_DEPLOY=1`, the dedicated checkout is clean, and the exact expected source commit is supplied. Treat the existing `ww-cx-website/scripts/deploy-business159.sh` as the deployment implementation; the operator is a safety/verification wrapper around it.

## Edge1

Use the established Edge1 authenticated operator/deployment procedure for the specific service/repository. Never substitute the Business159 shared-host model for Edge1 machine-level operations.

## Coordinated releases

Preflight each host independently, identify dependency order, deploy the least externally risky component first when architecture permits, then verify the full cross-host data path with `wwcx-cross-host-operator` semantics.

Never declare success because a command exited zero. Require functional verification. Roll back the affected host when post-release verification fails and a safe tested rollback is available. Preserve unrelated work and never force-push or rewrite shared Git history.
