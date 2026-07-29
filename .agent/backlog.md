# Backlog

## Completed

- [x] Deploy Security Correlation and Network Defense observability.
- [x] Pass read-only Security observability and `edge1.ww.cx` domain acceptance.
- [x] Deploy accessible Suricata drill-down, last-known-good caching, normalization, and source collector enrichment.
- [x] Verify 22 enriched alerts with ports, application protocol, SID/GID/revision, and flow ID.
- [x] Implement and deploy read-only Spamhaus live-state verification.
- [x] Confirm Spamhaus `active_verified`, enforcement verification true, and verified-enforcement count 1.
- [x] Confirm Network Defense remains `limited`, 6 of 7 sources are available, DNS policy is `not_staged`, DNS enforcement is disabled, and `traffic_controls_changed` is false.

## Authoritative evidence

```text
Security observability:
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z

edge1.ww.cx domain:
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z

Suricata normalization:
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z

Suricata collector enrichment:
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z

Spamhaus successful deployment and exact summary:
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json
```

## Current bounded implementation — Fail2ban live-state observability

- [x] Trace Fail2ban’s existing state to event-count visibility without service/socket/jail-health verification.
- [x] Add `server/fail2ban_live_state_verifier.py` with read-only `systemctl show` and `fail2ban-client status` inspection.
- [x] Restrict jail names to a bounded safe character set and a maximum of 64 records.
- [x] Publish service state, socket reachability, and aggregate/per-jail failed and banned counters.
- [x] Exclude banned addresses, log paths, raw client output, commands, credentials, and private keys.
- [x] Add `server/network_defense_fail2ban_exporter.py` so public status receives aggregate metrics only.
- [x] Keep Fail2ban `enforcement_verified: false`; jail counters do not increment verified enforcement.
- [x] Add a hardened root oneshot and one-minute timer with no Linux capabilities and AF_UNIX only.
- [x] Keep Network Defense capability-free and order it after both dedicated verifiers.
- [x] Add parser, privacy, stale-state, integration, runtime-wiring, and rollback-safe deployment validation.
- [x] Add `deploy/install-fail2ban-live-state-observability.sh` without any Fail2ban service or action mutation.
- [x] Record architecture, contract, state model, and activation boundary.
- [ ] Open and merge the Fail2ban observability PR after both required CI workflows pass.
- [ ] Fast-forward Edge1 and run `sudo bash ./deploy/install-fail2ban-live-state-observability.sh`.
- [ ] Record the truthful live state: `active_observed`, `partial`, `inactive`, `not_installed`, or `unavailable`.
- [ ] Verify Network Defense consumes the same aggregate state with `traffic_controls_changed: false` and no new enforcement claim.
- [ ] Record live evidence and close the phase.

## Evidence-driven follow-up

Optional future design work may:

- publish bounded general nftables aggregate counts through a separate least-privilege service;
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
