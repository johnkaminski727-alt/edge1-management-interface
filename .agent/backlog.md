# Backlog

## Completed

- [x] Pull current `main` on Edge1.
- [x] Deploy Security Correlation and Network Defense observability.
- [x] Capture sanitized firewall and Fail2ban posture.
- [x] Pass read-only Security observability acceptance.
- [x] Verify `edge1.ww.cx` DNS, Apache, TLS, pages, and live JSON feeds.
- [x] Deploy accessible Suricata alert expand/collapse and last-known-good caching.
- [x] Deploy nested Suricata alert normalization.
- [x] Verify classified alerts, known risk, schema `2.0`, live cache, read-only correlation, disabled enforcement, and unchanged traffic controls.
- [x] Trace missing metadata to the deployment-only Big Bird collector.
- [x] Establish `server/bigbird_ops_collect.py` as the authoritative Edge1 collector source.
- [x] Retain allowlisted ports, application protocol, SID/GID/revision, and flow/event identifiers.
- [x] Preserve the 100-alert source bound, 50-alert public bound, and payload/raw-event exclusion.
- [x] Add source-collector, source-to-exporter, and rollback-safe deployment validation.
- [x] Merge collector enrichment through PR #115 after both required CI workflows passed.
- [x] Fast-forward Edge1 and run `sudo bash ./deploy/activate-suricata-collector-enrichment.sh`.
- [x] Verify 22 of 22 live alerts with source and destination ports, application protocol, SID/GID/revision, and flow ID.
- [x] Refresh Security Operations, Correlation, and Network Defense and pass nested observability acceptance.
- [x] Record live collector enrichment evidence and close the phase.

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
```

## Evidence-driven follow-up

Optional future design work may:

- publish bounded nftables aggregate counts through a least-privilege service;
- publish bounded Fail2ban jail counters where socket permissions permit;
- add a Spamhaus live-state verifier distinguishing feed readiness from active enforcement;
- review Network Defense freshness thresholds using observed timing;
- design protected historical Suricata retention with size, time, privacy, authentication, rollback, and acceptance boundaries;
- review whether the public `edge1.ww.cx` access boundary should remain unchanged.

## Explicitly deferred

Requires exact production authorization and separate rollback/validation plans:

- Unbound or resolver configuration changes;
- RPZ inclusion, activation, reload, or DNS answer changes;
- firewall, nftables, Fail2ban, proxy, routing, IDS, or reputation-filter control changes;
- any additional public or production traffic cutover;
- authentication-boundary changes;
- any claim of active enforcement without direct evidence.