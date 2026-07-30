# Network Defense Freshness Policy Handoff

Date: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Implementation merge: `711952afb053fa3bd50c390516fa7b58f3943985`  
Implementation PR: `#126`

## Verified live baseline

- Network Defense and Security Correlation are deployed and accepted.
- Suricata drill-down, last-known-good caching, normalization, and source enrichment are live.
- Spamhaus is `active_verified` and remains the sole enforcement-verified source.
- Fail2ban is `active_observed` with service/socket health and 7 observed jails.
- General nftables aggregate visibility is `ruleset_observed`.
- Network Defense remains `limited`, 8 of 9 sources are available, DNS policy is `not_staged`, DNS enforcement is disabled, and traffic controls remain unchanged.

## Repository-complete implementation

The schedule-aware freshness improvement is merged.

Evidence:

- `wwcx-operations-network.timer` publishes every 300 seconds.
- `wwcx-network-defense.timer` consumes every 60 seconds with up to 10 seconds randomized delay.
- The prior 300-second network stale limit equaled the producer interval.
- The existing live-acceptance freshness ceiling is 600 seconds.

Change:

```text
network stale_after_seconds: 300 -> 600
```

The final wrapper preserves the nftables-, Fail2ban-, DNS-, Spamhaus-, Security Operations, Security Correlation, and operations-center layers. Every other source threshold remains unchanged.

## Validation and merge

Exact implementation head: `d2c6357cd913fa376f91b27e43081d1b1e37a6d6`

- `Validate repository` run 610: success.
- `Edge1 Operator Validation` run 442: success.
- PR #126 was mergeable and zero commits behind `main`.
- No unresolved review threads existed.
- Merged as `711952afb053fa3bd50c390516fa7b58f3943985`.

## Safety

No producer timer, collection command, DNS, Unbound, RPZ, nftables, firewall, Fail2ban jail/action, routing, proxy, IDS rule, reputation list, certificate, authentication boundary, or production traffic was changed.

The Network Defense unit remains capability-free and restricted to AF_UNIX. `verified_enforcement_count` semantics are unchanged and `traffic_controls_changed` remains false.

## Remaining live activation work

No authenticated Edge1 terminal was available in this runtime. Do not claim the freshness change is live until terminal evidence proves:

1. a clean Edge1 checkout was fast-forwarded to the authoritative merge;
2. the wrapper and unit were installed through a bounded rollback-safe procedure;
3. daemon reload and the one-shot exporter succeeded;
4. the generated snapshot reports `network.stale_after_seconds: 600`;
5. public and local endpoint checks pass without changing enforcement state;
6. protected evidence was captured.

## Next optional repository phase

Design protected historical Suricata retention with explicit size, time, privacy, authentication, rollback, and acceptance limits. Keep public `edge1.ww.cx` access-boundary review separate.

## Authoritative existing live evidence

```text
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z
/var/lib/wwcx-deployment-evidence/nftables-live-state/20260730T090522Z
```
