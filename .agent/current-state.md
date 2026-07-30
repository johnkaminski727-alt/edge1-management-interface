# Current State

Last verified: 2026-07-30 18:46 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Authoritative closeout commit: `bbefaca8fddc33270178daada5ca20ca3fce0c08`  
Current design branch: `design/suricata-protected-retention-20260730`

## Verified live security observability

- Network Defense and Security Correlation are deployed and accepted through `edge1.ww.cx`.
- Security Operations includes accessible Suricata drill-down, last-known-good caching, normalized schema `2.0`, and enriched allowlisted alert fields.
- Spamhaus is accepted as `active_verified` and remains the sole verified enforcement source.
- Fail2ban is accepted as `active_observed`; the service and local socket were healthy and all 7 reported jails were observed.
- General nftables aggregate visibility is accepted as `ruleset_observed`.
- Network Defense remains `limited`, 8 of 9 sources are available, DNS policy is `not_staged`, DNS enforcement is disabled, and traffic controls are unchanged.

## Freshness policy repository state

The schedule-aware Network Defense freshness policy is repository-complete through:

- implementation PR #126, merge `711952afb053fa3bd50c390516fa7b58f3943985`;
- repository closeout PR #127, merge `bbefaca8fddc33270178daada5ca20ca3fce0c08`.

The change is not claimed live because no authenticated Edge1 shell is available in this runtime.

## Current repository phase — protected Suricata retention design

A disabled, non-deploying design now defines the historical retention boundary.

Proposed limits:

- sanitized collector source only: `/var/lib/bigbird/operations-center/latest.json`;
- raw EVE access prohibited;
- 30-day operational target;
- 256 MiB hard database ceiling;
- 100,000 unique-event hard ceiling;
- pruning to at most 90 percent of capacity;
- root-only directory `0700` and files `0600`;
- deterministic SHA-256 deduplication;
- local root CLI only;
- default query 24 hours/100 rows, maximum seven days/500 rows;
- no listener, public endpoint, browser storage, or automatic off-host backup;
- incident promotion only through a separately authorized sanitized export with SHA-256 manifest and authorization record.

Assets:

- `config/security/suricata-protected-retention-policy.json`;
- `schemas/wwcx-suricata-protected-retention-policy-v1.schema.json`;
- `docs/security/suricata-protected-retention-design-20260730.md`;
- `registers/suricata-protected-retention-design-register-20260730.md`;
- `tests/validate_suricata_retention_design.py`.

The policy is `design_only`, `enabled: false`, and records `deployment_authorized: false`.

## Validation status

- Existing collector, exporter, drill-down/cache design, and records schedule were inspected.
- Static design validation was added.
- The current container cannot resolve `github.com`, so an isolated local clone could not be used for pre-PR execution.
- Exact-head GitHub CI remains the authoritative validation path for this branch.
- No runtime ingester, database, systemd unit, installer, API route, authentication change, or deployment exists.

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

## Safety boundary

Repository work is design-only. It does not authorize or make changes to Suricata configuration/service state, DNS, Unbound, RPZ, nftables, firewall, Fail2ban, routing, proxying, reputation lists, authentication, certificates, listeners, public access, deletion, or production traffic.
