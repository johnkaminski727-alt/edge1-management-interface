# Backlog

## Completed live phases

- [x] Security Correlation and Network Defense deployed and accepted.
- [x] Suricata drill-down, caching, normalization, and enrichment deployed.
- [x] Spamhaus, Fail2ban, and nftables truthful live states accepted.
- [x] DNS remains unstaged/disabled and traffic controls unchanged.

## Completed repository phases

- [x] Network Defense freshness closed through PR #127.
- [x] Protected Suricata retention design closed through PR #129.
- [x] Public access-boundary design closed through PR #131.
- [x] Minimized public summary passed exact-head CI and merged through PR #132 as `25359040ba07a3b7bf513f95b32ce24f6be480f2`.

## Minimized public summary acceptance

- [x] Define `wwcx.edge1-public-status.v1`.
- [x] Implement explicit-input, allowlist-only exporter.
- [x] Default output to repository build path, never `/var/www`.
- [x] Reduce Security, Network Defense, and Operations to state/count/freshness.
- [x] Cap counts and maintenance notice.
- [x] Degrade stale/missing sources without exposing errors or paths.
- [x] Add hostile fixtures and recursive forbidden-key/value tests.
- [x] Add non-routed page consuming only `./status.json`.
- [x] Add no-command/network/live-path/deployment/systemd validations.
- [x] Pass `Validate repository` run 622 and `Edge1 Operator Validation` run 454.
- [x] Confirm zero-behind, mergeable, and no unresolved review threads.
- [x] Merge and update closeout records.

## Remaining host/live work

Requires authenticated Edge1 execution and exact authorization where noted:

- [ ] activate and accept Network Defense freshness with terminal evidence;
- [ ] collect protected-retention host sizing/SQLite evidence before runtime implementation;
- [ ] capture read-only Apache/vhost/alias/auth/header/CORS/listing/route/filesystem inventory;
- [ ] design server-side minimized publication headers and ownership;
- [ ] prepare backup and rollback for any future public route change;
- [ ] obtain exact authorization before publishing minimized artifacts;
- [ ] stage authenticated detailed operations separately;
- [ ] cut over public access only under exact authorization and protected evidence.

## Explicitly not authorized

- `/var/www` publication or file removal;
- Apache/proxy/auth/header reload or route changes;
- authentication, certificate, listener, DNS, firewall, or traffic changes;
- public or production cutover;
- data/report/incident/status/evidence destruction.
