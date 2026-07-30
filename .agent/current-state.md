# Current State

Last verified: 2026-07-30 18:55 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Latest design merge: `13b87f876be3f6676b58863499d36395267fb870`  
Design PR: `#128`

## Verified live security observability

- Network Defense and Security Correlation are deployed and accepted through `edge1.ww.cx`.
- Security Operations includes accessible Suricata drill-down, last-known-good caching, normalized schema `2.0`, and enriched allowlisted alert fields.
- Spamhaus is accepted as `active_verified` and remains the sole verified enforcement source.
- Fail2ban is accepted as `active_observed`; the service and local socket were healthy and all 7 reported jails were observed.
- General nftables aggregate visibility is accepted as `ruleset_observed`.
- Network Defense remains `limited`, 8 of 9 sources are available, DNS policy is `not_staged`, DNS enforcement is disabled, and traffic controls are unchanged.

## Freshness policy repository state

The schedule-aware Network Defense freshness policy is repository-complete through PR #127 at `bbefaca8fddc33270178daada5ca20ca3fce0c08`.

The freshness change is not claimed live because no authenticated Edge1 shell is available in this runtime.

## Repository-complete protected retention design

PR #128 merged the disabled protected historical Suricata-retention design as `13b87f876be3f6676b58863499d36395267fb870`.

Accepted design limits:

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

The policy remains `design_only`, `enabled: false`, and `deployment_authorized: false`.

## Repository validation

Exact design head: `32dd1363ca3d1327dddaaddf9bba20b75514457d`

- `Validate repository` run 614: success;
- `Edge1 Operator Validation` run 446: success;
- PR mergeable and zero commits behind `main` before merge;
- no unresolved review threads;
- scope limited to policy, schema, design documentation, register, static validation, and `.agent` records;
- no runtime, systemd, public, API, authentication, or protected-control assets entered scope.

No runtime ingester, database, service, timer, query tool, evidence exporter, API route, authentication change, backup transfer, or Edge1 deployment exists.

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

## Next phase

The next separate repository phase is review of the public `edge1.ww.cx` access boundary. It must remain design-only unless a later exact authorization permits an authentication, certificate, proxy, listener, or public-access change.

## Safety boundary

Repository work remains non-deploying. It does not authorize or make changes to Suricata configuration/service state, DNS, Unbound, RPZ, nftables, firewall, Fail2ban, routing, proxying, reputation lists, authentication, certificates, listeners, public access, deletion, or production traffic.
