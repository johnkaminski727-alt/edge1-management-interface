# Backlog

## Completed live phases

- [x] Deploy and accept Security Correlation and Network Defense observability.
- [x] Deploy accessible Suricata drill-down, last-known-good caching, normalization, and source enrichment.
- [x] Accept Spamhaus as `active_verified`, the sole enforcement-verified source.
- [x] Accept Fail2ban as `active_observed` with service/socket health and 7 observed jails.
- [x] Deploy and accept sanitized general nftables aggregate visibility as `ruleset_observed`.
- [x] Confirm Network Defense remains `limited`, 8 of 9 sources are available, DNS policy is `not_staged`, DNS enforcement is disabled, and `traffic_controls_changed` is false.

## Current repository phase — freshness policy

- [x] Verify authoritative `main` at `d1a6a94568f235a2153e3f7946f9990b7a050547`.
- [x] Verify the operations-network producer interval is 300 seconds.
- [x] Verify the Network Defense consumer interval is 60 seconds with up to 10 seconds randomized delay.
- [x] Verify the established Security observability acceptance ceiling is 600 seconds.
- [x] Create focused branch `feature/network-defense-freshness-policy-20260730`.
- [x] Implement a final read-only wrapper that changes only the network-source stale threshold from 300 to 600 seconds.
- [x] Preserve every other source threshold.
- [x] Retain the capability-free AF_UNIX-only Network Defense service boundary.
- [x] Add focused threshold, hardening, and no-command/no-network tests.
- [x] Add architecture documentation and a sanitized implementation register.
- [ ] Pass targeted and full repository validation on the exact feature head.
- [ ] Confirm both required exact-head CI workflows succeed.
- [ ] Review scope, diff, unresolved threads, and mergeability.
- [ ] Merge only after all required checks pass.
- [ ] Update closeout documentation on authoritative `main`.

## Live activation boundary

Not included in the repository phase:

- [ ] Fast-forward a clean Edge1 checkout to the eventual merge commit.
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
