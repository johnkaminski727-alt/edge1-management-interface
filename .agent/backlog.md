# Backlog

## Completed

- [x] Pull current `main` on Edge1.
- [x] Deploy Security Correlation with `sudo bash ./deploy/install-security-correlation-observability.sh`.
- [x] Capture sanitized firewall and Fail2ban posture with `sudo bash ./tools/security/inspect-security-controls.sh`.
- [x] Rerun `sudo bash ./tools/security/verify-security-observability-live.sh` after the scheduled Network Defense refresh.
- [x] Record the successful acceptance evidence path and final sanitized summary.
- [x] Verify DNS, Apache virtual hosts, HTTP-to-HTTPS redirect, listeners, and the installed `edge1.ww.cx` certificate.
- [x] Verify the Operations Center, Security Operations, Security Correlation, and Network Defense pages through `https://edge1.ww.cx`.
- [x] Verify all three live JSON feeds through the domain and preserve the sanitized domain acceptance result.
- [x] Deploy accessible Suricata alert expand/collapse and Edge1 last-known-good caching.
- [x] Verify the live cache contract with `mode: live`, `stale: false`, and a bounded 30-alert snapshot.

Authoritative successful acceptance evidence:

```text
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z
```

Authoritative domain acceptance evidence:

```text
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z
```

## Current bounded implementation

- [x] Normalize nested Suricata signature, severity, ports, application protocol, rule identifiers, category, action, and flow/event ID in the repository.
- [x] Add sanitized schema metadata and payload/raw-event exclusion tests.
- [x] Enrich the alert drill-down panel with normalized metadata.
- [ ] Merge the normalization PR after both required CI workflows pass.
- [ ] Fast-forward Edge1, publish the enriched page, run the Security Operations exporter, and capture live acceptance evidence.
- [ ] Verify Security Correlation and Network Defense consume the refreshed Security Operations snapshot without any traffic-control change.

## Evidence-driven follow-up

The live Security Controls inspection confirmed both nftables and Fail2ban posture are readable through the bounded inspector. Optional follow-up design work may:

- decide whether nftables aggregate counts can be published periodically with a least-privilege service;
- decide whether Fail2ban socket access and jail counters support a safe periodic exporter;
- add a dedicated Spamhaus live-state verifier that distinguishes feed readiness from active nftables enforcement;
- review Network Defense freshness thresholds using actual correlation and control-inspection timing;
- design protected historical Suricata alert retention with a retention period, size cap, stable identifiers, authenticated query boundary, rollback, and acceptance checks;
- review whether the current `edge1.ww.cx` public access boundary should remain unchanged or receive a separately designed authentication or network restriction layer;
- avoid creating a permanent controls exporter or changing the access boundary until minimum permissions, ownership, sandbox, sanitized schema, rollback, and acceptance checks are defined.

## Explicitly deferred

Requires exact production authorization and separate rollback/validation plans:

- Unbound or resolver configuration changes;
- RPZ inclusion, activation, reload, or DNS answer changes;
- firewall, nftables, Fail2ban, proxy, routing, IDS, or reputation-filter control changes;
- any additional public or production traffic cutover;
- authentication-boundary changes;
- any claim of active enforcement without direct evidence.
