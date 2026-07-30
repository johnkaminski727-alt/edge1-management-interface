# Backlog

## Completed live phases

- [x] Security Correlation and Network Defense deployed and accepted.
- [x] Suricata drill-down, caching, normalization, and enrichment deployed.
- [x] Spamhaus, Fail2ban, and nftables truthful live states accepted.
- [x] DNS remains `not_staged`; DNS enforcement remains false.
- [x] Network Defense freshness threshold activated and accepted at `600` seconds.
- [x] Verified enforcement count remained `1` before and after activation.
- [x] Timer state and traffic controls remained unchanged.

## Completed repository phases

- [x] Network Defense freshness implementation and closeout through PR #127.
- [x] Protected Suricata retention design and closeout through PR #129.
- [x] Public access-boundary design and closeout through PR #131.
- [x] Minimized public summary implementation and closeout through PR #133.
- [x] Edge1 project completion operator bundle merged through PR #134.
- [x] Runtime-wiring validation corrected through PR #136 and merged as `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`.
- [x] Protected Suricata retention runtime and closeout merged through PRs #138 and #139.
- [x] Minimized public-summary route and CSP corrections merged through PRs #140 and #141.
- [x] Disabled public-summary staging runtime and closeout merged through PRs #144 and #145.
- [x] Authenticated detailed-operations browser/session boundary and closeout merged through PRs #146 and #147 as `a8af7fa77d9eb81ecd69d22e9d314de478975d66`.

## Completed authenticated host sequence

- [x] Establish authenticated SSH access to `edge1.ww.cx` as `wwadmin` without sharing credentials.
- [x] Fast-forward clean `/opt/edge1-management-interface` checkout to authoritative `main`.
- [x] Run the read-only project completion preflight.
- [x] Capture protected preflight evidence at `/var/lib/wwcx-deployment-evidence/edge1-project-completion-preflight/20260730T193415Z`.
- [x] Safely stop the first freshness activation during pre-mutation validation.
- [x] Pull the PR #136 correction and run bounded freshness activation successfully.
- [x] Capture protected activation evidence at `/var/lib/wwcx-deployment-evidence/network-defense-freshness/20260730T195031Z`.

## Protected Suricata retention runtime

- [x] Add fail-closed runtime, hardened proposed units, tests, and register.
- [x] Pass exact-head workflows and merge through PR #138; close through PR #139.
- [ ] Design a separate bounded installer and live acceptance only after exact authorization.

## Minimized public summary staging runtime

- [x] Reconcile the canonical route and strict CSP.
- [x] Add disabled policy, immutable release builder, SHA-256 metadata, proposed units, strict Apache proposal, tests, and records.
- [x] Pass exact-head workflows and merge through PR #144; close through PR #145.
- [ ] Re-run fresh authenticated Edge1 boundary inventory before any staging installation.
- [ ] Design a bounded installer and staging acceptance only after exact authorization.

## Authenticated detailed-operations browser/session boundary

- [x] Add disabled policy, OIDC/session requirements, exact routes/scopes, pure evaluator, denied Apache design, tests, and records.
- [x] Pass exact-head workflows and merge through PR #146; close through PR #147.
- [ ] Run a fresh authenticated Edge1 module, route, provider, session-store, audit, and rate-limit inventory.
- [ ] Select and verify an identity provider and Apache adapter under separate authorization.
- [ ] Implement and stage the restricted session boundary only after exact authorization.

## Restricted artifact migration manifest

- [x] Inventory repository-declared detailed Operations Center pages and feeds.
- [x] Add a disabled exact source-to-target manifest.
- [x] Record 23 exact artifacts and five live-enumerated prefix groups.
- [x] Validate every target against the registered restricted routes and general detail scope.
- [x] Add a read-only SHA-256 inventory reconciler.
- [x] Preserve unknown artifacts for review, report missing known files, and block target collisions.
- [x] Keep staging, cutover, deletion, and source mutation disabled.
- [x] Add synthetic coverage, mapping, metadata, privacy, and non-mutation tests.
- [x] Add architecture and audit records.
- [ ] Pass exact-head `Validate repository` workflow.
- [ ] Pass exact-head `Edge1 Operator Validation` workflow.
- [ ] Complete changed-file, zero-behind, mergeability, and review-thread checks.
- [ ] Merge repository-only migration design and close records.
- [ ] Run a fresh authenticated live filesystem, route, publisher, service, and SHA-256 inventory.
- [ ] Reconcile all unknown, missing, prefix-contained, duplicate, stale, historical, and operator-maintained artifacts.

## Separate future program

- [ ] staged public-boundary cutover and detailed-artifact removal.

## Exact authorization still required

- production Suricata-history database creation, unit installation, timer enablement, or ingestion;
- public-summary staging-root creation, unit installation, timer enablement, or service invocation on Edge1;
- identity-provider registration, credentials, client secrets, user/group/scope mapping, session-store creation, or authentication changes;
- restricted release creation or source-tree copying on Edge1;
- `/var/www` publication or removal;
- Apache/proxy/auth/header reload or route changes;
- certificate, listener, DNS, firewall, or traffic changes;
- public or production cutover;
- deletion or pruning of retained status, releases, reports, incidents, history, audit, or evidence.
