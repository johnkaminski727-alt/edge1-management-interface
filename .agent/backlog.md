# Backlog

## Completed live phases

- [x] Deploy and accept Security Correlation and Network Defense observability.
- [x] Deploy accessible Suricata drill-down, caching, normalization, and source enrichment.
- [x] Accept Spamhaus as `active_verified`, Fail2ban as `active_observed`, and nftables as `ruleset_observed`.
- [x] Preserve DNS `not_staged`, DNS enforcement disabled, and `traffic_controls_changed:false`.

## Completed repository phases

- [x] Network Defense freshness closed through PR #127.
- [x] Protected Suricata retention design closed through PR #129.
- [x] Edge1 public access boundary design passed exact-head CI and merged through PR #130 as `6e0bbb9d38cd2b89a5ba59ced1534a93ba3aa2eb`.

## Pending live activation — freshness

- [ ] Establish an authenticated Edge1 execution path.
- [ ] Fast-forward a clean checkout, activate the wrapper/unit through rollback-safe procedure, verify endpoints, and capture evidence.

## Pending implementation — protected retention

- [ ] Collect alert-size/rate, filesystem, and SQLite evidence.
- [ ] Implement ingester, service/timer, CLI, evidence export, pruning, rollback, and later live acceptance on separate branches.

## Completed design — public access boundary

- [x] Classify the existing `/edge1-status/` tree as a mixed boundary.
- [x] Decide the unchanged mixed boundary is not the safest long-term design.
- [x] Define a minimized public landing page and allowlist-only status feed.
- [x] Classify detailed security, topology, change, automation, incident, communications, financial, and report/evidence data as restricted.
- [x] Define a future authenticated, fail-closed operations surface.
- [x] Define header, CORS, directory-listing, staging, rollback, and acceptance requirements.
- [x] Pass `Validate repository` run 618 and `Edge1 Operator Validation` run 450.
- [x] Confirm zero-behind, mergeable, and no unresolved review threads.
- [x] Merge PR #130 and update closeout records.

## Next repository phase — minimized public summary

Allowed without live routing or publication:

- [ ] define `wwcx.edge1-public-status.v1` schema;
- [ ] implement allowlist-only exporter consuming existing snapshots;
- [ ] add fixtures proving sensitive fields never propagate;
- [ ] add a static public landing page consuming only the minimized summary;
- [ ] write output only to a repository build/test path by default;
- [ ] add validation proving no deploy script, systemd unit, Apache change, or `/var/www` default;
- [ ] require exact-head CI and merge review.

## Public-boundary live implementation boundary

Not authorized:

- live Apache/vhost/alias/auth/header changes;
- authenticated browser/session activation;
- proxy/path staging or public cutover;
- publication or removal under `/var/www`;
- service reload, certificate, listener, DNS, firewall, or traffic change.

## Explicitly deferred

Requires exact authorization and separate rollback/validation:

- resolver/RPZ changes;
- firewall, nftables, Fail2ban, proxy, routing, IDS, or reputation control changes;
- certificate or authentication-boundary changes;
- public/production cutover;
- destruction of retained data, reports, incidents, status files, or evidence.
