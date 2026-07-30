# Network Defense Freshness Policy Handoff

Date: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Authoritative synchronized closeout: `d1a6a94568f235a2153e3f7946f9990b7a050547`  
Feature branch: `feature/network-defense-freshness-policy-20260730`

## Verified live baseline

- Network Defense and Security Correlation are deployed and accepted.
- Suricata drill-down, last-known-good caching, normalization, and source enrichment are live.
- Spamhaus is `active_verified` and remains the sole enforcement-verified source.
- Fail2ban is `active_observed` with service/socket health and 7 observed jails.
- General nftables aggregate visibility is `ruleset_observed`.
- Network Defense remains `limited`, 8 of 9 sources are available, DNS policy is `not_staged`, DNS enforcement is disabled, and traffic controls remain unchanged.

## Current implementation

A narrow schedule-aware freshness improvement is implemented on the feature branch.

Evidence:

- `wwcx-operations-network.timer` publishes every 300 seconds.
- `wwcx-network-defense.timer` consumes every 60 seconds with up to 10 seconds randomized delay.
- The prior 300-second network stale limit equaled the producer interval and could classify healthy data stale between normal runs.
- The existing live-acceptance freshness ceiling is 600 seconds.

Change:

```text
network stale_after_seconds: 300 -> 600
```

Assets:

- `server/network_defense_freshness_exporter.py`
- `deploy/systemd/wwcx-network-defense.service`
- `tests/test_network_defense_freshness_policy.py`
- `docs/security/network-defense-freshness-policy-20260730.md`
- `registers/network-defense-freshness-policy-register-20260730.md`

The wrapper leaves every other source threshold unchanged and preserves the final DNS-, Spamhaus-, Fail2ban-, and nftables-aware exporter chain.

## Safety

No producer timer, collection command, DNS, Unbound, RPZ, nftables, firewall, Fail2ban jail/action, routing, proxy, IDS rule, reputation list, certificate, authentication boundary, or production traffic was changed.

The Network Defense unit remains capability-free and restricted to AF_UNIX. `verified_enforcement_count` semantics are unchanged and `traffic_controls_changed` remains false.

## Validation state

Completed:

- authoritative branch and base commit verification;
- schedule and acceptance-threshold inspection;
- focused implementation review;
- test and documentation additions.

Pending:

- targeted tests on the exact feature head;
- full repository validation;
- both required exact-head CI workflows;
- PR scope, thread, review, and mergeability checks;
- merge and authoritative-main closeout.

No authenticated Edge1 terminal was available in the current runtime. No live deployment or endpoint acceptance is claimed.

## Required next sequence

1. Open the focused PR from `feature/network-defense-freshness-policy-20260730` to `main`.
2. Require both exact-head workflows: `Validate repository` and `Edge1 Operator Validation`.
3. Inspect the final diff and ensure no unrelated files or protected controls changed.
4. Merge only if checks pass and the PR is mergeable with no unresolved review threads.
5. Update `.agent` and register closeout on authoritative `main`.
6. Treat Edge1 activation as a separate bounded terminal-evidence phase.

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
