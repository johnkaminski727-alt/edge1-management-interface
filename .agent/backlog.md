# Backlog

## Completed live phases

- [x] Security Correlation and Network Defense deployed and accepted.
- [x] Suricata drill-down, caching, normalization, and enrichment deployed.
- [x] Network Defense freshness threshold activated and accepted at `600` seconds.
- [x] Verified enforcement count remained `1` before and after activation.
- [x] DNS remains `not_staged`; DNS enforcement remains false.
- [x] Timer state and traffic controls remained unchanged.

## Completed repository phases

- [x] Protected Suricata retention runtime and closeout through PRs #138-139.
- [x] Minimized public-summary route, CSP, staging runtime, and closeout through PRs #140-145.
- [x] Authenticated detailed-operations browser/session boundary and closeout through PRs #146-147.
- [x] Restricted-artifact migration manifest and closeout through PRs #148-149.
- [x] Security-boundary live inventory bundle merged through PR #151 as `85d9a9cb43e5ca4dd09f2d955b00997ef28e2cf0`.

## Security-boundary live inventory bundle

- [x] Record the exact four-program authorization and immutable guardrails without secrets.
- [x] Add clean-`main`, root, command, and authorization preflight gates.
- [x] Capture host, principal, capacity, repository revision, listeners, and relevant service state.
- [x] Capture redacted unit definitions and Apache syntax/vhost/module readiness.
- [x] Hash Apache configuration without copying configuration contents.
- [x] Generate exact JSON path/SHA-256/mode/byte inventory for the detailed public tree.
- [x] Report symlink and non-regular-file anomalies.
- [x] Reconcile live inventory against the merged migration manifest and access policy.
- [x] Preserve unknown artifacts for review and report missing known artifacts.
- [x] Capture anonymous local/public route and security-header matrices without credentials or cookie values.
- [x] Capture metadata-only candidate-root, audit-log, and retention-tree inventories.
- [x] Add evidence redactor and synthetic functional/static safety tests.
- [x] Add operator runbook, audit register, and continuity records.
- [x] Pass exact-head `Validate repository` run 662.
- [x] Pass exact-head `Edge1 Operator Validation` run 494.
- [x] Confirm 11 changed files, zero-behind state, mergeability, and zero unresolved review threads.
- [x] Merge through PR #151 as `85d9a9cb43e5ca4dd09f2d955b00997ef28e2cf0`.
- [ ] Run the merged script through an approved authenticated Edge1 path.
- [ ] Record the exact protected evidence directory and reconciliation counts.

## Post-inventory implementation sequence

- [ ] Reconcile every unknown, missing, prefix-contained, duplicate, stale, historical, and operator-maintained artifact.
- [ ] Verify an actually available approved identity provider and Apache adapter without placing secrets in Git or chat.
- [ ] Build a restricted release without changing the source tree.
- [ ] Stage and accept authenticated `/edge1-ops/` before anonymous withdrawal.
- [ ] Install and accept minimized public-summary staging.
- [ ] Install and accept protected Suricata retention.
- [ ] Archive the detailed public tree and perform the minimized public cutover only after authenticated equivalence succeeds.
- [ ] Confirm anonymous detailed routes are withdrawn, authenticated routes remain functional, listeners remain unchanged, and rollback is not required.

## Hard boundaries

- Never place credentials, client secrets, password hashes, tokens, cookies, private keys, or raw alert contents in Git or evidence.
- Never modify DNS, Unbound, RPZ, nftables, firewall rules, routing, IDS rules, reputation lists, certificates, or production traffic under this program.
- Never delete retained status, releases, reports, incidents, history, audit, or deployment evidence.
- Roll back immediately if authentication, route isolation, public minimization, service health, data integrity, or listener equivalence fails.
