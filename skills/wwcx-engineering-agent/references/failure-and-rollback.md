# Failure and Rollback

Use this guide whenever validation fails, a deployment changes runtime state, or the observed system diverges from the expected result.

## Failure classification

Classify the failure before acting:

- **Development failure** — tests, lint, static analysis, build, or packaging failed before deployment.
- **Integration failure** — branch, merge, dependency, schema, or CI behavior differs from the local result.
- **Deployment failure** — artifact installation, migration, reload, restart, listener, health check, or fresh log validation failed.
- **Evidence failure** — the system may be healthy, but the available evidence is stale, incomplete, contradictory, or from the wrong environment.
- **Authority failure** — the next corrective action requires access or authorization that is not available.

Do not treat an evidence or authority failure as proof that the software itself is defective.

## Immediate response

1. Stop the failing step from progressing further.
2. Preserve the first useful error, exit code, timestamp, affected environment, branch or artifact version, and relevant logs.
3. Determine whether the action changed persistent or live state.
4. Continue independent safe diagnostics and fixes.
5. Roll back promptly when a live change is unhealthy and a tested rollback path exists.

Do not repeatedly retry a destructive or state-changing action without new evidence or a corrective change.

## Development rollback

For repository-only work:

- prefer a corrective commit over rewriting shared history;
- do not force-push unless the user explicitly authorizes it and no safer path exists;
- do not discard unrelated working-tree changes;
- preserve failing tests that accurately expose the defect;
- revert generated artifacts when they are stale or invalid.

## Deployment rollback

Before a live change, identify:

- the previously known-good artifact or commit;
- configuration backup or prior version;
- migration reversibility and data-loss risk;
- the exact rollback command;
- the health checks that prove rollback success.

Rollback when any required health criterion fails and forward repair is not clearly safer and faster.

After rollback, verify independently:

- service state;
- expected process or listener;
- health endpoint or functional smoke test;
- fresh logs after the rollback time;
- restored artifact or configuration version.

A successful command is not proof of a successful rollback.

## Database and irreversible changes

Treat destructive migrations, data deletion, key rotation, certificate replacement, DNS changes, firewall changes, authentication changes, and live routing changes as separately protected operations. Do not improvise a rollback for them. Stop before execution unless the authority and tested recovery plan explicitly cover the action.

## Partial completion

When one action is blocked or fails:

- finish all independent safe work;
- record the exact blocked action;
- state what evidence is already complete;
- provide the smallest next action needed to resume;
- do not label the project complete while required validation remains unresolved.

## Completion after failure

Close the task only when one terminal condition is true:

1. the intended change is validated in the target environment;
2. the system is validated after rollback to the prior known-good state;
3. all safe work is complete and the remaining action is explicitly blocked by missing authority, access, credentials, payment, legal acceptance, or another protected dependency.
