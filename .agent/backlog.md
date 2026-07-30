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
- [x] Edge1 project completion operator bundle merged through PR #134 as `00904a2d26b4b3b14e18144c9bccd29b3a9f10b1`.
- [x] Runtime-wiring validation corrected through PR #136 and merged as `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`.
- [x] Protected Suricata retention runtime merged through PR #138 as `98d4d2bb2b3f57b54f3ca6f1779ec9fd2d4ab694`.
- [x] Protected-retention closeout merged through PR #139 as `4b14a3c513dd7878c0d8c2ee4fa751f292e7bb6a`.
- [x] Minimized public-summary route contract corrected through PR #140 as `4fc5d765805b86be8ddee58f08c2676116517cbb`.
- [x] Minimized public-summary CSP contract corrected through PR #141 as `feb771b6ab53ed9547fec81dbaea964a0246f27d`.
- [x] Disabled public-summary staging runtime merged through PR #144 as `86a906a536bbb785d47e249615d9c22e411d2ac3`.

## Completed authenticated host sequence

- [x] Establish authenticated SSH access to `edge1.ww.cx` as `wwadmin` without sharing credentials.
- [x] Fast-forward clean `/opt/edge1-management-interface` checkout to authoritative `main`.
- [x] Run the read-only project completion preflight.
- [x] Capture protected preflight evidence at `/var/lib/wwcx-deployment-evidence/edge1-project-completion-preflight/20260730T193415Z`.
- [x] Safely stop the first freshness activation during pre-mutation validation.
- [x] Pull the PR #136 correction and run bounded freshness activation successfully.
- [x] Capture protected activation evidence at `/var/lib/wwcx-deployment-evidence/network-defense-freshness/20260730T195031Z`.

## Protected Suricata retention runtime

- [x] Add fail-closed sanitized-alert retention, deduplication, pruning, bounded query runtime, hardened proposed units, tests, and register.
- [x] Pass exact-head `Validate repository` run 640 and `Edge1 Operator Validation` run 472.
- [x] Merge PR #138 and close records through PR #139.
- [ ] Design a separate bounded installer and live acceptance only after exact authorization.

## Minimized public summary staging runtime

- [x] Reconcile the canonical `/edge1-status/public/status.json` route.
- [x] Externalize CSS and align the page to the strict approved CSP.
- [x] Add a disabled staging policy and schema.
- [x] Add a fail-closed immutable release builder with exact asset allowlisting.
- [x] Add atomic current-pointer selection and private SHA-256 metadata.
- [x] Add hardened proposed systemd service and 60-second timer.
- [x] Add an explicitly non-active Apache alias/header proposal.
- [x] Add temporary-directory functional, privacy, permission, and static safety tests.
- [x] Add architecture and audit records.
- [x] Pass exact-head `Validate repository` run 649.
- [x] Pass exact-head `Edge1 Operator Validation` run 481.
- [x] Complete changed-file, zero-behind, mergeability, and review-thread checks.
- [x] Merge repository-only staging runtime through PR #144 as `86a906a536bbb785d47e249615d9c22e411d2ac3`.
- [ ] Re-run fresh authenticated Edge1 boundary inventory before any staging installation.
- [ ] Design a bounded installer and staging acceptance only after exact authorization.

## Separate future programs

Require new branches, measured host evidence, exact-head CI, and separate deployment acceptance:

- [ ] authenticated detailed-operations browser/session design;
- [ ] staged public-boundary cutover and detailed-artifact removal.

## Exact authorization still required

- production Suricata-history database creation, unit installation, timer enablement, or ingestion;
- public-summary staging-root creation, unit installation, timer enablement, or service invocation on Edge1;
- `/var/www` publication or removal;
- Apache/proxy/auth/header reload or route changes;
- authentication, certificate, listener, DNS, firewall, or traffic changes;
- public or production cutover;
- deletion or pruning of retained status, releases, reports, incidents, history, or evidence.
