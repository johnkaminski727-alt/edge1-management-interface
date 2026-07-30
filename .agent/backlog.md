# Backlog

## Completed live phases

- [x] Deploy and accept Security Correlation and Network Defense observability.
- [x] Deploy accessible Suricata drill-down, last-known-good caching, normalization, and source enrichment.
- [x] Accept Spamhaus as `active_verified`, the sole enforcement-verified source.
- [x] Accept Fail2ban as `active_observed` with service/socket health and 7 observed jails.
- [x] Deploy and accept sanitized general nftables aggregate visibility as `ruleset_observed`.
- [x] Confirm Network Defense remains `limited`, 8 of 9 sources are available, DNS policy is `not_staged`, DNS enforcement is disabled, and `traffic_controls_changed` is false.

## Completed repository phase — freshness policy

- [x] Merge schedule-aware freshness implementation through PR #126 as `711952afb053fa3bd50c390516fa7b58f3943985`.
- [x] Merge repository closeout through PR #127 as `bbefaca8fddc33270178daada5ca20ca3fce0c08`.
- [x] Preserve every other source threshold and the full layered exporter chain.
- [x] Retain the capability-free AF_UNIX-only Network Defense service boundary.

## Freshness live activation boundary

Not completed or claimed:

- [ ] Establish an authenticated Edge1 execution path.
- [ ] Verify a clean Edge1 checkout and fast-forward it to authoritative `main`.
- [ ] Install the freshness wrapper and updated systemd unit through a bounded rollback-safe procedure.
- [ ] Run daemon reload and the one-shot exporter without changing producer timers or traffic controls.
- [ ] Verify service result, source threshold, endpoint state, and unchanged enforcement count.
- [ ] Capture protected terminal evidence before claiming live deployment.

## Current design phase — protected Suricata retention

- [x] Inspect the sanitized collector and Security Operations exporter contracts.
- [x] Separate historical retention from the live 50-alert snapshot and last-known-good cache.
- [x] Define a disabled policy contract and JSON schema.
- [x] Prohibit raw EVE access, raw logs, packet payloads, arbitrary metadata, credentials, and private keys.
- [x] Define a 30-day target, 256 MiB hard ceiling, and 100,000-event hard ceiling.
- [x] Define deterministic SHA-256 deduplication and a unique event key.
- [x] Define root-only storage modes and no public/static output.
- [x] Define local CLI query limits: default 24 hours/100 rows; maximum seven days/500 rows.
- [x] Defer future authenticated API access to a separate review using scope `security.suricata.history.read`.
- [x] Define manual incident promotion with authorization record and SHA-256 manifest.
- [x] Define rollback that preserves the database by default and never touches Suricata or traffic controls.
- [x] Add static repository validation.
- [ ] Pass exact-head `Validate repository` and `Edge1 Operator Validation` workflows.
- [ ] Review PR scope, mergeability, and unresolved threads.
- [ ] Merge the design phase and update authoritative closeout records.

## Explicitly not started

Requires a separate implementation branch, exact-head validation, and later authenticated deployment evidence:

- runtime SQLite ingester;
- systemd service or timer;
- database or status-file creation;
- local query CLI;
- evidence-export command;
- Edge1 activation;
- any API route or authentication-boundary change;
- any off-host backup.

## Separate future phase

- [ ] Review whether the public `edge1.ww.cx` access boundary should remain unchanged.

## Explicitly deferred

Requires exact production authorization and separate rollback/validation plans:

- Unbound or resolver configuration changes;
- RPZ inclusion, activation, reload, or DNS answer changes;
- firewall, nftables, Fail2ban jail/action, proxy, routing, IDS, or reputation-filter control changes;
- certificate or authentication-boundary changes;
- any additional public or production traffic cutover;
- destruction of retained security data or evidence packages.
