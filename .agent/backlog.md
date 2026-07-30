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

## Current phase — operator completion bundle

- [x] Add bounded Network Defense freshness activation.
- [x] Require clean `main` and the merged freshness commit.
- [x] Back up installed unit and current snapshot before mutation.
- [x] Preserve timer enablement, active state, and schedule.
- [x] Verify threshold `600`, unchanged enforcement count, DNS `not_staged`, DNS enforcement false, and no traffic-control change.
- [x] Add automatic rollback and protected evidence capture.
- [x] Add read-only Apache/vhost/auth/header/CORS/listing/route/filesystem inventory.
- [x] Add SQLite and sanitized Suricata retention-sizing evidence.
- [x] Stage the minimized summary only beneath protected evidence.
- [x] Add shell-syntax and static safety validation.
- [x] Add runbook, register, current-state, backlog, and handoff updates.
- [ ] Pass exact-head `Validate repository`.
- [ ] Pass exact-head `Edge1 Operator Validation`.
- [ ] Confirm changed-file scope, zero-behind state, mergeability, and no unresolved review threads.
- [ ] Merge and close the repository phase.

## Remaining authenticated host sequence

- [ ] Fast-forward a clean Edge1 checkout to authoritative `main`.
- [ ] Run `sudo bash tools/security/edge1-project-completion-preflight.sh`.
- [ ] Review the protected preflight result and evidence manifest.
- [ ] Run `sudo bash deploy/activate-network-defense-freshness.sh`.
- [ ] Confirm local and public acceptance, rollback state false, and protected evidence.
- [ ] Update repository records with exact host evidence paths and live result.

## Separate future programs

Require new branches and evidence from the preflight:

- [ ] protected Suricata retention runtime implementation, tests, deployment, and acceptance;
- [ ] minimized public summary server-side publication design;
- [ ] authenticated detailed-operations browser/session design;
- [ ] staged public-boundary cutover and detailed-artifact removal.

## Exact authorization still required

- `/var/www` publication or removal;
- Apache/proxy/auth/header reload or route changes;
- authentication, certificate, listener, DNS, firewall, or traffic changes;
- public or production cutover;
- deletion of retained status, report, incident, or evidence data.
