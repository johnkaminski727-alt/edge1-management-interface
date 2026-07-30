# Backlog

## Completed live phases

- [x] Deploy and accept Security Correlation and Network Defense observability.
- [x] Deploy Suricata drill-down, caching, normalization, and source enrichment.
- [x] Accept Spamhaus, Fail2ban, and nftables truthful live states.
- [x] Preserve DNS `not_staged`, DNS enforcement disabled, and no traffic-control change.

## Completed repository phases

- [x] Network Defense freshness closed through PR #127.
- [x] Protected Suricata retention design closed through PR #129.
- [x] Public access-boundary design closed through PR #131 at `1d995bbc0ec9029c9853d9968470f248eb8b6995`.

## Pending live/host phases

- [ ] Establish authenticated Edge1 execution.
- [ ] Activate and accept the freshness change with terminal evidence.
- [ ] Collect host evidence before protected-retention implementation.
- [ ] Capture read-only Apache/auth/header/route/filesystem inventory before any public-boundary change.

## Current repository phase — minimized public summary

- [x] Define schema `wwcx.edge1-public-status.v1`.
- [x] Implement allowlist-only exporter with required explicit source paths.
- [x] Default output to `build/edge1-public-status/status.json`, never `/var/www`.
- [x] Reduce Security to health state, alert count, and freshness only.
- [x] Reduce Network Defense to overall state, available-source count, and freshness only.
- [x] Reduce Operations Health to overall state, check count, and freshness only.
- [x] Cap counts and maintenance notice.
- [x] Degrade stale/missing sources without exposing errors or paths.
- [x] Add hostile fixtures with topology, addresses, ports, IDs, Git, incidents, services, and reports.
- [x] Recursively validate forbidden keys and hostile-value exclusion.
- [x] Add static page and external renderer consuming only `./status.json`.
- [x] Add CSP meta, no-referrer, omitted credentials, and browser no-store behavior.
- [x] Add no-command, no-network, no-live-path, no-deploy, and no-systemd validations.
- [x] Add implementation documentation and register.
- [ ] Pass exact-head `Validate repository` and `Edge1 Operator Validation`.
- [ ] Confirm changed-file scope, zero-behind, mergeability, and no unresolved threads.
- [ ] Merge and close the repository phase.

## Explicitly not implemented or authorized

- deploy script or systemd unit;
- Apache/vhost/alias/header changes;
- `/var/www` output or publication;
- public route activation or cutover;
- authenticated operations UI/session;
- removal of existing detailed files;
- DNS, certificate, listener, firewall, proxy, or traffic changes.

## Explicitly deferred

- protected-retention runtime and deployment;
- authentication-boundary implementation;
- public/production cutover;
- data/report/incident/status/evidence destruction.
