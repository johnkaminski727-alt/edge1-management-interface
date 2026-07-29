# Backlog

## Completed

- [x] Deploy Security Correlation and Network Defense observability.
- [x] Pass read-only Security observability and `edge1.ww.cx` domain acceptance.
- [x] Deploy accessible Suricata drill-down and last-known-good caching.
- [x] Deploy nested Suricata normalization and source collector enrichment.
- [x] Verify 22 enriched alerts with ports, application protocol, SID/GID/revision, and flow ID.
- [x] Preserve bounded alert counts and payload/raw-event exclusion.
- [x] Implement read-only Spamhaus live-state verification.
- [x] Publish contract `wwcx.spamhaus-live-state.v1` with bounded counts and booleans only.
- [x] Confine `CAP_NET_ADMIN` to the dedicated verifier service; keep Network Defense capability-free.
- [x] Integrate fresh complete verifier evidence into Network Defense as `active_verified` when warranted.
- [x] Withdraw verified enforcement when verifier evidence becomes stale.
- [x] Add rollback-safe installer and full parser, privacy, runtime, systemd, and deployment validation.
- [x] Merge PR #118 after both required CI workflows passed.
- [x] Repair the case-sensitive runtime wording assertion through PR #119.
- [x] Run the corrected installer successfully on Edge1.
- [x] Record successful evidence directory and unchanged traffic-control boundary.
- [x] Read and record the exact acceptance summary.
- [x] Confirm Spamhaus state `active_verified`, enforcement verification true, and verified-enforcement count 1.
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

Spamhaus failed attempt, safely rolled back:
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180002Z

Spamhaus successful deployment:
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z

Spamhaus exact acceptance summary:
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json
```

## Evidence-driven follow-up

Optional future design work may:

- publish bounded general nftables aggregate counts through a separate least-privilege service;
- publish bounded Fail2ban jail counters where socket permissions permit;
- review Network Defense freshness thresholds using observed timing;
- design protected historical Suricata retention with size, time, privacy, authentication, rollback, and acceptance boundaries;
- review whether the public `edge1.ww.cx` access boundary should remain unchanged.

## Explicitly deferred

Requires exact production authorization and separate rollback/validation plans:

- Unbound or resolver configuration changes;
- RPZ inclusion, activation, reload, or DNS answer changes;
- firewall, nftables, Fail2ban, proxy, routing, IDS, or reputation-filter control changes;
- any additional public or production traffic cutover;
- authentication-boundary changes.
