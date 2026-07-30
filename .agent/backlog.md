# Backlog

## Completed

- [x] Deploy Security Correlation and Network Defense observability.
- [x] Pass read-only Security observability and `edge1.ww.cx` domain acceptance.
- [x] Deploy accessible Suricata drill-down, last-known-good caching, normalization, and source collector enrichment.
- [x] Verify 22 enriched alerts with ports, application protocol, SID/GID/revision, and flow ID.
- [x] Implement and deploy read-only Spamhaus live-state verification.
- [x] Confirm Spamhaus `active_verified`, enforcement verification true, and verified-enforcement count 1.
- [x] Implement, deploy, and accept read-only Fail2ban live-state observability.
- [x] Confirm Fail2ban `active_observed`, service/socket health, 7 observed jails, zero accepted ban counters, and no enforcement claim.
- [x] Confirm DNS policy remains `not_staged`, DNS enforcement is disabled, and `traffic_controls_changed` is false.

## Authoritative live evidence

```text
Security observability:
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z

edge1.ww.cx domain:
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z

Suricata normalization:
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z

Suricata collector enrichment:
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z

Spamhaus live-state:
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json

Fail2ban live-state:
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z/acceptance-summary.json
```

## Current bounded implementation — general nftables aggregate visibility

- [x] Define contract `wwcx.nftables-aggregate-live-state.v1`.
- [x] Add a dedicated verifier that executes only `nft -j list ruleset` and `systemctl show nftables.service`.
- [x] Reduce the full ruleset to numeric object, family, hook, policy, verdict, element, packet, and byte aggregates.
- [x] Exclude names, addresses, prefixes, ports, interfaces, devices, elements, rule expressions, comments, handles, priorities, jump targets, raw output, credentials, and private keys.
- [x] Keep `enforcement_verified: false` and `traffic_controls_changed: false` in every state.
- [x] Add truthful `ruleset_observed`, `partial`, `empty`, `not_installed`, and `unavailable` states.
- [x] Add `server/network_defense_nftables_exporter.py` as the final layered exporter over DNS, Spamhaus, and Fail2ban.
- [x] Keep public Network Defense aggregate-only and keep verified-enforcement count unchanged.
- [x] Add hardened root oneshot and 60-second timer with only `CAP_NET_ADMIN`, `AF_UNIX`, and `AF_NETLINK`.
- [x] Keep `wwcx-network-defense.service` capability-free.
- [x] Add parser, privacy, stale-state, layered-integration, runtime-wiring, deployment-safety, and rollback validation.
- [x] Add rollback-safe `deploy/install-nftables-live-state-observability.sh` without nftables or firewall mutation.
- [x] Update legacy Network Defense, Spamhaus, and Fail2ban validators for the final layered wrapper.
- [x] Record architecture, contract, state model, repository audit trail, and activation boundary.
- [ ] Open and merge the nftables aggregate observability PR after both required CI workflows pass.
- [ ] Fast-forward Edge1 and run `sudo bash ./deploy/install-nftables-live-state-observability.sh`.
- [ ] Record the truthful live state and sanitized aggregate counts.
- [ ] Verify Network Defense consumes the same state without a new enforcement claim.
- [ ] Record live evidence and close the phase.

## Evidence-driven follow-up

Optional future design work may:

- review Network Defense freshness thresholds using observed timing;
- design protected historical Suricata retention with size, time, privacy, authentication, rollback, and acceptance boundaries;
- review whether the public `edge1.ww.cx` access boundary should remain unchanged.

## Explicitly deferred

Requires exact production authorization and separate rollback/validation plans:

- Unbound or resolver configuration changes;
- RPZ inclusion, activation, reload, or DNS answer changes;
- firewall, nftables, Fail2ban jail/action, proxy, routing, IDS, or reputation-filter control changes;
- any additional public or production traffic cutover;
- authentication-boundary changes.
