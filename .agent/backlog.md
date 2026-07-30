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
- [x] Authenticated detailed-operations browser/session boundary merged through PR #146 as `a0dd8103d8035862d03769ef4fabb0359cc73009`.

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

- [x] Add disabled browser/session policy and critical JSON schema.
- [x] Require OIDC authorization code, PKCE S256, state, nonce, issuer/audience validation, MFA, and external provider configuration.
- [x] Define opaque server-side sessions, secure cookie, timeout, rotation, and logout/CSRF requirements.
- [x] Define exact registered route and scope matrix under `/edge1-ops/`.
- [x] Add pure fail-closed path, identity, scope, rate-limit, and redacted-audit evaluator.
- [x] Add exact 404, 401, 403, 405, and 429 contracts.
- [x] Add strict restricted-response headers and no-CORS contract.
- [x] Add credential-free Apache `.design` with unconditional deny gates.
- [x] Add policy drift, ambiguity, session, scope, privacy, and static boundary tests.
- [x] Add architecture and audit register.
- [x] Pass exact-head `Validate repository` run 653.
- [x] Pass exact-head `Edge1 Operator Validation` run 485.
- [x] Confirm 10 expected files, zero-behind, mergeable state, and no review threads.
- [x] Merge repository-only authenticated-boundary design through PR #146 as `a0dd8103d8035862d03769ef4fabb0359cc73009`.
- [ ] Run a fresh authenticated Edge1 module, route, provider, session-store, audit, and rate-limit inventory.
- [ ] Select and verify an identity provider and Apache adapter under separate authorization.
- [ ] Implement and stage the restricted session boundary only after exact authorization.

## Separate future program

- [ ] staged public-boundary cutover and detailed-artifact removal.

## Exact authorization still required

- production Suricata-history database creation, unit installation, timer enablement, or ingestion;
- public-summary staging-root creation, unit installation, timer enablement, or service invocation on Edge1;
- identity-provider registration, credentials, client secrets, user/group/scope mapping, session-store creation, or authentication changes;
- `/var/www` publication or removal;
- Apache/proxy/auth/header reload or route changes;
- certificate, listener, DNS, firewall, or traffic changes;
- public or production cutover;
- deletion or pruning of retained status, releases, reports, incidents, history, audit, or evidence.
