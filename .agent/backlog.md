# Backlog

## Completed live phases

- [x] Deploy and accept Security Correlation and Network Defense observability.
- [x] Deploy accessible Suricata drill-down, last-known-good caching, normalization, and source enrichment.
- [x] Accept Spamhaus as `active_verified`, the sole enforcement-verified source.
- [x] Accept Fail2ban as `active_observed` with service/socket health and 7 observed jails.
- [x] Deploy and accept sanitized general nftables aggregate visibility as `ruleset_observed`.
- [x] Confirm Network Defense remains `limited`, 8 of 9 sources are available, DNS policy is `not_staged`, DNS enforcement is disabled, and `traffic_controls_changed` is false.

## Completed repository phases

- [x] Close Network Defense freshness through PR #127 at `bbefaca8fddc33270178daada5ca20ca3fce0c08`.
- [x] Close protected Suricata retention design through PR #129 at `74323ce0d572806278afe400f3c1e9e244e89d10`.

## Pending live activation — freshness

- [ ] Establish an authenticated Edge1 execution path.
- [ ] Verify a clean Edge1 checkout and fast-forward it to authoritative `main`.
- [ ] Install the freshness wrapper/unit through a bounded rollback-safe procedure.
- [ ] Verify source threshold, endpoint state, unchanged enforcement count, and protected terminal evidence.

## Pending implementation — protected retention

Requires a separate branch and host evidence:

- [ ] representative sanitized alert-size and unique-rate measurements;
- [ ] Edge1 free-space, SQLite version, and page-limit evidence;
- [ ] runtime ingester, service/timer, local CLI, evidence exporter, and pruning/rollback tests;
- [ ] any API/authentication phase;
- [ ] Edge1 activation and live acceptance.

## Current design phase — public access boundary

- [x] Review accepted `edge1.ww.cx` pages and JSON feeds.
- [x] Inspect the Operations Center publisher and browser dependencies.
- [x] Inspect host inventory, network, version, changes, automation, incident, communications/carrier, and report exporters.
- [x] Classify the current `/edge1-status/` tree as a mixed boundary requiring review.
- [x] Decide that the unchanged mixed boundary is not the safest long-term design.
- [x] Define a minimized public landing page and allowlist-only aggregate status contract.
- [x] Classify detailed security, topology, change, automation, incident, communications, financial, and evidence surfaces as restricted.
- [x] Define a future authenticated, fail-closed operations surface without selecting or activating browser authentication.
- [x] Define cache, CSP, referrer, content-type, CORS, and directory-listing acceptance requirements.
- [x] Define read-only inventory, parallel build, authenticated staging, public cutover, and artifact-removal phases.
- [x] Define rollback preserving operational data.
- [x] Add disabled policy, schema, design, register, and static validation.
- [ ] Pass exact-head `Validate repository` and `Edge1 Operator Validation` workflows.
- [ ] Confirm zero-behind state, mergeability, scope, and no unresolved review threads.
- [ ] Merge and close the repository design phase.

## Public-boundary implementation boundary

Explicitly not started and not authorized:

- [ ] live Apache/vhost/alias/auth/header inventory;
- [ ] minimized public exporter and landing page implementation;
- [ ] authenticated browser/session design;
- [ ] proxy or path staging;
- [ ] public cutover;
- [ ] removal of detailed public artifacts;
- [ ] any Apache reload, auth, certificate, listener, DNS, filesystem-publication, or public-access change.

## Explicitly deferred

Requires exact production authorization and separate rollback/validation plans:

- Unbound or resolver configuration changes;
- RPZ inclusion, activation, reload, or DNS answer changes;
- firewall, nftables, Fail2ban jail/action, proxy, routing, IDS, or reputation-filter control changes;
- certificate or authentication-boundary changes;
- any additional public or production traffic cutover;
- destruction of retained security data, reports, incidents, status files, or evidence packages.
