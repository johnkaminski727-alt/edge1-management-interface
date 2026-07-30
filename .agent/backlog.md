# Backlog

## Completed live phases

- [x] Deploy and accept Security Correlation and Network Defense observability.
- [x] Deploy accessible Suricata drill-down, last-known-good caching, normalization, and source enrichment.
- [x] Accept Spamhaus as `active_verified`, the sole enforcement-verified source.
- [x] Accept Fail2ban as `active_observed` with service/socket health and 7 observed jails.
- [x] Deploy and accept sanitized general nftables aggregate visibility as `ruleset_observed`.
- [x] Confirm Network Defense remains `limited`, 8 of 9 sources are available, DNS policy is `not_staged`, DNS enforcement is disabled, and `traffic_controls_changed` is false.

## Completed repository phase — freshness policy

- [x] Verify producer and consumer schedules and the established 600-second acceptance ceiling.
- [x] Implement a final read-only wrapper changing only the network-source stale threshold from 300 to 600 seconds.
- [x] Preserve every other source threshold and the full layered exporter chain.
- [x] Retain the capability-free AF_UNIX-only Network Defense service boundary.
- [x] Add focused and legacy-chain validation coverage.
- [x] Pass exact-head `Validate repository` run 610.
- [x] Pass exact-head `Edge1 Operator Validation` run 442.
- [x] Confirm scope, zero-behind state, mergeability, and no unresolved review threads.
- [x] Merge PR #126 as `711952afb053fa3bd50c390516fa7b58f3943985`.
- [x] Update repository closeout records.

## Live activation boundary

Not completed or claimed:

- [ ] Verify a clean Edge1 checkout and fast-forward it to the repository merge.
- [ ] Install the wrapper and updated systemd unit through a bounded, rollback-safe operator procedure.
- [ ] Run daemon reload and the one-shot exporter without changing producer timers or traffic controls.
- [ ] Verify service result, generated snapshot, source threshold, endpoint state, and unchanged enforcement count.
- [ ] Capture protected terminal evidence before claiming live deployment.

## Next optional design phase

- [ ] Design protected historical Suricata retention with explicit size, time, privacy, authentication, rollback, and acceptance limits.
- [ ] Keep review of the public `edge1.ww.cx` access boundary as a separate design phase.

## Explicitly deferred

Requires exact production authorization and separate rollback/validation plans:

- Unbound or resolver configuration changes;
- RPZ inclusion, activation, reload, or DNS answer changes;
- firewall, nftables, Fail2ban jail/action, proxy, routing, IDS, or reputation-filter control changes;
- certificate or authentication-boundary changes;
- any additional public or production traffic cutover.
