# Protected Suricata Retention Design Handoff

Date: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Design merge: `13b87f876be3f6676b58863499d36395267fb870`  
Design PR: `#128`

## Verified live baseline

- Network Defense and Security Correlation are deployed and accepted.
- Suricata drill-down, last-known-good caching, normalization, and source enrichment are live.
- Spamhaus is `active_verified` and remains the sole enforcement-verified source.
- Fail2ban is `active_observed` with service/socket health and 7 observed jails.
- General nftables aggregate visibility is `ruleset_observed`.
- Network Defense remains `limited`, 8 of 9 sources are available, DNS policy is `not_staged`, DNS enforcement is disabled, and traffic controls remain unchanged.

## Freshness phase

The Network Defense freshness repository phase is closed through PR #127 at `bbefaca8fddc33270178daada5ca20ca3fce0c08`.

The freshness change is not claimed live. No authenticated Edge1 shell is available in this runtime.

## Repository-complete retention design

PR #128 merged the disabled protected history design for already-sanitized Suricata alerts.

Machine-readable contract:

```text
wwcx.suricata-protected-retention-policy.v1
```

Assets:

```text
config/security/suricata-protected-retention-policy.json
schemas/wwcx-suricata-protected-retention-policy-v1.schema.json
docs/security/suricata-protected-retention-design-20260730.md
registers/suricata-protected-retention-design-register-20260730.md
tests/validate_suricata_retention_design.py
```

The policy remains `design_only`, `enabled: false`, and `deployment_authorized: false`.

## Accepted design decisions

- Read only `/var/lib/bigbird/operations-center/latest.json` and require `wwcx.suricata-source-alert.v1`.
- Never open raw Suricata EVE logs from a future history component.
- Retain up to 30 days, 256 MiB, or 100,000 unique alerts, whichever limit is reached first.
- Use SHA-256 canonical event keys and a database unique constraint for deduplication.
- Store under `/var/lib/bigbird-security/suricata-history` as `root:root`, directory `0700`, files `0600`.
- Create no listener, HTTP route, static history JSON, browser storage, or public page.
- Initial queries are root-local CLI only, default 24 hours/100 rows, maximum seven days/500 rows.
- Future API access requires separate authorization and the existing authenticated operations API scope `security.suricata.history.read`.
- Automatic off-host backup is disabled.
- Incident promotion is manual and separately authorized, with sanitized rows, SHA-256 manifest, and authorization record.
- Rollback preserves the database by default; deletion requires separate records authority.

## Records boundary

The rolling 30-day store is operational telemetry, not the authoritative incident archive. Selected alerts for an incident, audit, hold, or legal preservation need must be promoted into a separate evidence package under:

```text
/var/lib/wwcx-deployment-evidence/suricata-history-holds/<UTC timestamp>/
```

The promoted package receives the appropriate security/evidence retention class.

## Validation and merge

Exact design head: `32dd1363ca3d1327dddaaddf9bba20b75514457d`

- `Validate repository` run 614: success.
- `Edge1 Operator Validation` run 446: success.
- PR #128 was mergeable and zero commits behind `main`.
- No unresolved review threads existed.
- Changed scope contained policy, schema, documentation, register, static validation, and `.agent` records only.
- Merged as `13b87f876be3f6676b58863499d36395267fb870`.

The local container could not resolve `github.com`, so GitHub exact-head CI was the authoritative execution path.

## Explicitly not implemented

- SQLite ingester or database;
- service or timer;
- query CLI;
- evidence-export command;
- API route;
- authentication change;
- public endpoint;
- off-host backup;
- Edge1 deployment.

## Pre-implementation evidence still required

- representative sanitized alert sizes and unique-event rates;
- Edge1 free-space and growth tolerance;
- SQLite version and page-limit behavior;
- root-only CLI sufficiency;
- records-custodian treatment of promoted incident exports;
- backup requirements, if any;
- future service account and systemd sandbox;
- rollback and temporary-database pruning tests.

## Next separate phase

Review the public `edge1.ww.cx` access boundary using repository evidence only. Inventory routes, endpoint data classes, cache behavior, and intended audiences. Do not modify proxying, authentication, certificates, listeners, DNS, or public access during that design phase.

## Safety boundary

No Suricata configuration/service state, DNS, Unbound, RPZ, nftables, firewall, Fail2ban jail/action, routing, proxy, reputation list, certificate, authentication boundary, listener, public access, deletion, or production traffic is changed or authorized by this design.
