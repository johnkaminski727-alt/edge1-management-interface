# Backlog

## Completed

- [x] Deploy Security Correlation and Network Defense observability.
- [x] Pass read-only Security observability and `edge1.ww.cx` domain acceptance.
- [x] Deploy accessible Suricata drill-down, last-known-good caching, normalization, and source collector enrichment.
- [x] Verify 22 enriched alerts with ports, application protocol, SID/GID/revision, and flow ID.
- [x] Implement and deploy read-only Spamhaus live-state verification.
- [x] Confirm Spamhaus `active_verified`, enforcement verification true, and verified-enforcement count 1.
- [x] Implement and merge read-only Fail2ban live-state observability through PR #122.
- [x] Deploy the Fail2ban verifier and timer on Edge1 without changing `fail2ban.service` or any jail/action.
- [x] Confirm Fail2ban state `active_observed`, service active, socket reachable, and all 7 reported jails observed.
- [x] Confirm currently banned 0, total banned 0, and `enforcement_verified: false` by design.
- [x] Confirm Network Defense consumes the same aggregate state, remains `limited`, has 7 of 8 sources available, and retains verified-enforcement count 1 from Spamhaus only.
- [x] Confirm DNS policy remains `not_staged`, DNS enforcement is disabled, and `traffic_controls_changed` is false.

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

Fail2ban successful deployment and exact summary:
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z/acceptance-summary.json
```

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
