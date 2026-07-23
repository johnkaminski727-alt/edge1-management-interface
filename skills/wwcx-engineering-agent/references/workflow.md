# Execution Workflow

## 1. Establish ground truth

- Confirm host, repository path, current branch, HEAD, remote HEAD, and working tree.
- Inspect relevant services, logs, CI, documentation, and recent commits.
- Reconcile conflicting reports with direct evidence.

## 2. Protect existing work

- Stash or commit unrelated local work before branch changes.
- Create a backup branch when branch history may matter.
- Never reset or delete work without verified recovery evidence.

## 3. Diagnose before editing

- Reproduce the failure with the narrowest command.
- Inspect the full affected file, not only the reported line.
- Sweep related files for the same corruption or drift pattern.
- Distinguish stale logs from current failures.

## 4. Implement

- Prefer the smallest complete repair.
- Fix deployment automation so manual recovery steps are not required again.
- Align service names, paths, users, ownership, configuration, and validators.
- Add branch guards and preflight checks when deployment context matters.

## 5. Validate

Run checks in this order when applicable:

1. static syntax and formatting;
2. targeted unit tests;
3. integration tests;
4. installer or deployment dry checks;
5. service restart and active/enabled checks;
6. listener and health endpoint checks;
7. fresh logs after the final start;
8. Git status, commit, push, and remote synchronization.

## 6. Publish and record

- Commit coherent changes.
- Push to the appropriate branch.
- Open or update a PR when branch protection requires it.
- Update runbooks, project state, validation evidence, and handoff.

## 7. Continue autonomously

Do not pause for routine confirmation. Move to the next safe item until complete. Stop only at an explicit authority boundary or when all remaining work depends on unavailable access.
