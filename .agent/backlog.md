# Backlog

## Completed live phases

- [x] Security Correlation and Network Defense deployed and accepted.
- [x] Suricata drill-down, caching, normalization, and enrichment deployed.
- [x] Spamhaus, Fail2ban, and nftables truthful live states accepted.
- [x] DNS remains unstaged/disabled and traffic controls unchanged.

## Completed repository phases

- [x] Network Defense freshness implementation and closeout through PR #127.
- [x] Protected Suricata retention design and closeout through PR #129.
- [x] Public access-boundary design and closeout through PR #131.
- [x] Minimized public summary implementation and closeout through PR #133.
- [x] Edge1 project completion operator bundle merged through PR #134 as `00904a2d26b4b3b14e18144c9bccd29b3a9f10b1`.
- [x] Pass exact-head `Validate repository` run 626.
- [x] Pass exact-head `Edge1 Operator Validation` run 458.
- [x] Confirm zero-behind state, mergeability, scope, and no unresolved review threads.

## Remaining authenticated host sequence

- [ ] Establish an approved authenticated Edge1 shell without sharing credentials in chat.
- [ ] Fast-forward a clean `/opt/edge1-management-interface` checkout to authoritative `main`.
- [ ] Run `sudo bash tools/security/edge1-project-completion-preflight.sh`.
- [ ] Review the protected preflight result and SHA-256 evidence manifest.
- [ ] Run `sudo bash deploy/activate-network-defense-freshness.sh`.
- [ ] Confirm local and public acceptance, unchanged timer/enforcement/DNS state, `rolled_back=false`, and protected evidence.
- [ ] Update records with exact host evidence paths and live acceptance results.

## Separate future programs

Require new branches, measured host evidence, exact-head CI, and separate deployment acceptance:

- [ ] protected Suricata retention runtime implementation;
- [ ] minimized public summary server-side publication design;
- [ ] authenticated detailed-operations browser/session design;
- [ ] staged public-boundary cutover and detailed-artifact removal.

## Exact authorization still required

- `/var/www` publication or removal;
- Apache/proxy/auth/header reload or route changes;
- authentication, certificate, listener, DNS, firewall, or traffic changes;
- public or production cutover;
- deletion of retained status, report, incident, or evidence data.
