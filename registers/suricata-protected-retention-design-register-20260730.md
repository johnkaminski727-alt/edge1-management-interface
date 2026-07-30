# Protected Suricata Retention Design Register

Date: 2026-07-30  
Classification: internal, security-sensitive design; no alert data  
System: Edge1 / WW.CX Security Operations  
Repository state: design branch only

## Trigger

The current Security Operations endpoint publishes only the newest 50 sanitized alerts and its last-known-good snapshot is a continuity cache rather than a historical database. Historical retention was explicitly deferred until size, time, privacy, authentication, rollback, and acceptance limits were defined.

## Evidence reviewed

| Evidence | Verified fact |
| --- | --- |
| `server/bigbird_ops_collect.py` | Collector emits `wwcx.suricata-source-alert.v1`, newest 100 alerts, and excludes payloads/raw events/credentials/private keys |
| `server/security_operations_exporter.py` | Public snapshot emits `wwcx.suricata-alert.v1`, newest 50 alerts, with bounded last-known-good fallback |
| `docs/security/suricata-alert-drilldown-and-cache-plan-20260729.md` | History remains separate and must not be exposed as an unbounded public archive |
| `docs/records-management/02-records-retention-schedule.md` | Operational logs default to three years, security records seven years, and convenience/transitory copies normally no more than 90 days; holds override disposition |

The design treats the rolling database as short-lived operational telemetry. Selected incident evidence must be promoted into a separate controlled evidence package and assigned the appropriate records class.

## Registered design assets

| Asset | Purpose | State |
| --- | --- | --- |
| `config/security/suricata-protected-retention-policy.json` | Disabled machine-readable limits and safety gates | Designed; disabled |
| `schemas/wwcx-suricata-protected-retention-policy-v1.schema.json` | Contract constraints for the disabled policy | Designed |
| `docs/security/suricata-protected-retention-design-20260730.md` | Architecture, privacy, authentication, capacity, rollback, and acceptance design | Designed |
| `tests/validate_suricata_retention_design.py` | Static design and boundary validation | Designed |

## Accepted design decisions

| Dimension | Decision |
| --- | --- |
| Runtime state | `design_only`, `enabled: false`, `deployment_authorized: false` |
| Ingestion source | Sanitized `/var/lib/bigbird/operations-center/latest.json` only |
| Raw EVE access | Prohibited |
| Retention target | 30 days |
| Database hard limit | 256 MiB |
| Event hard limit | 100,000 unique alerts |
| Headroom target | Prune to at most 90 percent of hard capacity |
| Database path | `/var/lib/bigbird-security/suricata-history/alerts.sqlite3` |
| Initial permissions | root-only directory `0700`, files `0600` |
| Deduplication | Deterministic SHA-256 event key with a unique constraint |
| Initial query surface | Local root CLI only |
| Query limits | Default 24 hours/100 rows; maximum seven days/500 rows |
| Public endpoint | Prohibited |
| Network listener | Prohibited |
| Future API | Separate authorization through existing Edge1 Operations API scope `security.suricata.history.read` |
| Automatic off-host backup | Disabled and deferred |
| Incident promotion | Manual, authorized, sanitized export with SHA-256 manifest |
| Rollback data handling | Preserve database by default; destruction separately authorized |

## Privacy boundary

The design retains only fields already allowlisted by the sanitized collector contract. It excludes packet payloads, raw EVE JSON, raw logs, arbitrary metadata, credentials, private keys, certificate material, application bodies, and command output.

Source and destination addresses are operationally sensitive historical data. They remain root-only and may not be published under `/var/www` or exposed through `edge1.ww.cx`.

## Records boundary

The 30-day rolling history is not the authoritative incident archive. A documented incident, hold, audit, or legal preservation need requires a separately authorized export under:

```text
/var/lib/wwcx-deployment-evidence/suricata-history-holds/<UTC timestamp>/
```

The export must contain a SHA-256 manifest and authorization record. Its retention is then governed by the assigned security/evidence record class rather than the rolling database policy.

## Validation state

| Validation | State |
| --- | --- |
| Existing source and public schema inspected | Passed |
| Explicit time, byte, event, and query limits | Defined |
| Disabled-by-default contract | Defined |
| Raw EVE and public exposure prohibition | Defined |
| Root-only initial authorization boundary | Defined |
| Incident promotion and records boundary | Defined |
| Rollback preserving data by default | Defined |
| Static repository validation | Pending exact-head CI |
| Runtime implementation | Not started |
| Edge1 deployment | Not authorized or performed |
| Live acceptance | Not performed |

## Required pre-implementation evidence

Before runtime code is approved, collect or verify:

- representative sanitized alert record sizes and unique-alert rates;
- free space and growth tolerance on the intended Edge1 filesystem;
- SQLite version and page-limit behavior;
- whether a root-only CLI is sufficient for the first operational phase;
- records-custodian treatment of promoted incident exports;
- backup requirements, if any;
- exact service account and systemd sandbox for a future ingester;
- rollback and temporary-database pruning tests.

These checks may tighten the limits. They must not expand them without review.

## Explicit non-authorization

This design does not authorize runtime code, database creation, systemd installation, daemon reload, Suricata restart or reload, API or authentication changes, public access, backup transfer, deletion, or production activation.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, Fail2ban jail/action, routing, proxy, IDS rule, reputation list, certificate, authentication boundary, listener, public endpoint, or production traffic is changed.
