# Current State

Last verified: 2026-07-30 18:35 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Authoritative synchronized closeout: `d1a6a94568f235a2153e3f7946f9990b7a050547`  
Current feature branch: `feature/network-defense-freshness-policy-20260730`  
Latest implementation merge: `6b7991b1e37c327813199057c90cf2a9f834aa14`

## Verified live security observability

- Network Defense and Security Correlation are deployed and accepted through `edge1.ww.cx`.
- Security Operations includes accessible Suricata drill-down, last-known-good caching, normalized schema `2.0`, and enriched allowlisted alert fields.
- Spamhaus is accepted as `active_verified` and remains the sole verified enforcement source.
- Fail2ban is accepted as `active_observed`; the service and local socket were healthy and all 7 reported jails were observed.
- General nftables aggregate visibility is accepted as `ruleset_observed`.
- Network Defense remains `limited`, 8 of 9 sources are available, DNS policy is `not_staged`, DNS enforcement is disabled, and traffic controls are unchanged.

## Current repository phase

The highest-value optional read-only item is a schedule-aware Network Defense freshness policy.

Verified repository timing:

- `wwcx-operations-network.timer`: 300-second producer interval;
- `wwcx-security-operations.timer`: 120-second interval;
- `wwcx-security-correlation.timer`: 60-second interval;
- `wwcx-network-defense.timer`: 60-second interval with up to 10 seconds randomized delay;
- Security observability live acceptance: 600-second default freshness ceiling.

The prior network-source stale limit was 300 seconds, equal to its producer interval. That can mark healthy source data stale between normal producer runs.

Implemented on the feature branch:

- `server/network_defense_freshness_exporter.py` sets only the network-source threshold to 600 seconds;
- `deploy/systemd/wwcx-network-defense.service` invokes the final freshness wrapper while retaining its capability-free AF_UNIX-only boundary;
- `tests/test_network_defense_freshness_policy.py` covers threshold boundaries, unchanged peer thresholds, service hardening, and no command/network execution;
- architecture documentation and a sanitized register record the evidence, limits, rollback, validation, and deployment boundary.

No timer interval, producer, DNS, resolver, RPZ, nftables, firewall, Fail2ban, routing, proxy, IDS rule, reputation list, authentication boundary, certificate, or production traffic was changed.

## Validation status

- Authoritative GitHub `main` was verified at `d1a6a94568f235a2153e3f7946f9990b7a050547` before branch creation.
- The prior closeout commit had both required workflows successful.
- Feature-branch targeted tests and full exact-head CI remain pending.
- No authenticated Edge1 shell was available in this runtime.
- No live deployment or live acceptance is claimed.

## Authoritative live evidence

```text
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z
/var/lib/wwcx-deployment-evidence/nftables-live-state/20260730T090522Z
```

## Safety boundary

Repository work remains read-only observability only. Live deployment requires separate terminal evidence and must not modify traffic controls or protected production boundaries.
