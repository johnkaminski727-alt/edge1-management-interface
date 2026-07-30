# Protected Historical Suricata Retention Design

Date: 2026-07-30  
System: Edge1 / WW.CX Security Operations  
Status: repository design only; disabled and not deployed

## Objective

Define a bounded local history for already-sanitized Suricata alerts without retaining raw EVE events, changing IDS behavior, exposing a public archive, or creating a new authentication boundary.

The design separates three different purposes:

1. the live Security Operations snapshot remains the newest 50 alerts;
2. last-known-good caching remains a continuity fallback, not history;
3. protected historical retention is a separate root-only store for short operational investigation windows.

## Evidence basis

The source-controlled collector already:

- reads the local Suricata EVE stream;
- emits only allowlisted alert fields under `wwcx.suricata-source-alert.v1`;
- excludes packet payloads, raw EVE events, credentials, private keys, and arbitrary metadata;
- publishes at most 100 recent normalized alerts in `/var/lib/bigbird/operations-center/latest.json`.

The Security Operations exporter then applies schema `wwcx.suricata-alert.v1` and publishes at most 50 alerts to the current public status snapshot.

The history design must consume the sanitized collector document. It must not open `/var/log/suricata/eve.json` or any other raw Suricata log.

## Policy contract

Authoritative disabled policy:

```text
config/security/suricata-protected-retention-policy.json
```

Schema:

```text
schemas/wwcx-suricata-protected-retention-policy-v1.schema.json
```

Contract:

```text
wwcx.suricata-protected-retention-policy.v1
```

The committed policy is `design_only`, has `enabled: false`, and records `deployment_authorized: false`.

## Retention and capacity limits

The proposed initial operational window is bounded by all three limits; the first limit reached controls:

- time target: 30 days;
- hard database size: 256 MiB;
- hard event count: 100,000 unique alerts.

SQLite page size is fixed at 4,096 bytes and `max_page_count` is fixed at 65,536, producing the 256 MiB hard ceiling. Normal pruning targets 90 percent of the hard capacity so collection has headroom.

The 30-day period is an operational investigation window, not the retention period for an incident record. Alerts selected for an incident, audit, legal hold, or security case must be promoted through a separately authorized evidence export with a SHA-256 manifest and authorization record. Promoted security records follow the records schedule; the rolling history database does not become a permanent incident archive.

Automatic off-host backup is disabled in the initial design. A backup destination, encryption/key custody, restore test, and retention class require a separate design and authorization.

## Proposed storage layout

```text
/var/lib/bigbird-security/suricata-history/
  alerts.sqlite3
  status.json
```

Initial permissions:

- directory: `root:root`, mode `0700`;
- database: `root:root`, mode `0600`;
- status file: `root:root`, mode `0600`.

No file is written under `/var/www`, and no compatibility symlink or public static endpoint is created.

## Ingestion boundary

A future oneshot ingester may run every 120 seconds, matching the current Security Operations refresh cadence. It may read only:

```text
/var/lib/bigbird/operations-center/latest.json
```

It must:

1. require the collector alert schema `wwcx.suricata-source-alert.v1`;
2. accept at most 100 alerts per run;
3. revalidate every approved field and length/range bound;
4. reject nested arbitrary objects and unknown fields;
5. calculate a deterministic SHA-256 `event_key` from canonical approved fields;
6. enforce a unique constraint on `event_key` so repeated snapshots do not duplicate rows;
7. prune by event time, event count, and database capacity;
8. atomically publish only a root-only aggregate status document.

The proposed canonical deduplication fields are recorded in the disabled policy. The canonical representation must use stable key ordering, explicit null values, UTF-8, and no locale-dependent formatting.

## Proposed database model

The implementation should remain intentionally small:

### `alerts`

- `event_key TEXT PRIMARY KEY`;
- `event_time TEXT NOT NULL`;
- `ingested_at TEXT NOT NULL`;
- `risk TEXT NOT NULL`;
- `signature_id INTEGER`;
- `flow_id TEXT`;
- `schema_version TEXT NOT NULL`;
- `payload_json TEXT NOT NULL` containing only the approved normalized fields.

Indexes should be limited to event time, risk, and signature ID. No raw-event column, packet column, BLOB payload, arbitrary metadata column, or command output is permitted.

### `ingest_runs`

- run timestamp;
- source generation time;
- accepted, duplicate, rejected, pruned, and retained counts;
- database bytes and state label;
- no alert contents or client-identifying log excerpt.

Truthful state labels should include:

- `disabled`;
- `healthy`;
- `capacity_limited`;
- `source_unavailable`;
- `schema_rejected`;
- `storage_error`.

A degraded state must not trigger a Suricata restart, rule reload, firewall change, or traffic-control repair.

## Privacy boundary

Allowed historical fields are limited to the existing sanitized alert contract:

- timestamp;
- signature and risk/severity;
- category and action;
- source and destination with bounded ports;
- protocol and application protocol;
- signature, generator, revision, flow, and event identifiers.

Excluded everywhere:

- packet bodies or payloads;
- raw EVE JSON;
- raw Suricata logs;
- TLS keys, credentials, tokens, passwords, private keys, or certificates;
- arbitrary nested metadata;
- file contents, DNS payload contents, HTTP bodies, or extracted application data;
- unbounded comments or command output.

Endpoint addresses are operationally sensitive even though they are already allowlisted in the live sanitized schema. Historical copies remain root-only and must not be exposed through the public status domain.

## Authentication and query limits

Initial query access is local CLI only and depends on root filesystem authorization. The initial design creates:

- no TCP or UDP listener;
- no HTTP route;
- no static JSON history file;
- no browser storage;
- no public `edge1.ww.cx` history page.

A future query tool must default to 24 hours and 100 rows, and enforce maximums of seven days and 500 rows per invocation.

Future API exposure, if separately approved, must use the existing authenticated Edge1 Operations API and a dedicated read scope:

```text
security.suricata.history.read
```

That future phase must separately review principal authorization, audit logging, rate limits, response minimization, and the public/private access boundary. This design does not authorize an authentication change.

## Capacity and pruning behavior

Pruning order:

1. remove rows older than 30 days unless already exported under a documented hold;
2. remove oldest rows above 100,000 events;
3. remove oldest rows until page use returns to at most 90 percent of the hard page cap;
4. run only bounded incremental reclamation, never an unbounded timer-time `VACUUM`.

When safe pruning cannot restore headroom, ingestion must stop with `capacity_limited`; it must not exceed the hard database limit or delete a promoted evidence export.

## Incident promotion and holds

Promotion is manual and separately authorized. A future evidence-export command must:

- require an explicit time/event selection and authorization record;
- export only sanitized rows;
- include policy version, query parameters, row count, earliest/latest event time, and exporter revision;
- produce a SHA-256 manifest;
- write under `/var/lib/wwcx-deployment-evidence/suricata-history-holds/<UTC timestamp>/`;
- never silently extend the rolling database retention period.

Destruction of a history database or promoted evidence package is not part of rollback and requires separate records-disposition authority.

## Rollback

A future deployment must use a separate service and timer so rollback does not alter the existing collector or Security Operations exporter.

Rollback sequence:

1. stop and disable only the future history timer;
2. stop only the future history oneshot if active;
3. restore or remove only the new unit and ingester assets;
4. run daemon reload;
5. verify Security Operations and the current live snapshot remain unchanged;
6. preserve the database by default for review;
7. destroy retained data only under separate explicit authorization.

No Suricata service restart, rule reload, network change, or public endpoint change belongs in rollback.

## Required implementation validation

Before any deployment, repository tests must prove:

- policy and schema consistency;
- disabled-by-default and explicit-authorization gates;
- source is the sanitized collector document and raw EVE access is absent;
- approved-field-only validation;
- deterministic deduplication and unique enforcement;
- time, count, page, and byte limits;
- root-only modes and atomic status publication;
- bounded queries and no listener/public route;
- capacity-limited behavior without control-plane remediation;
- incident export hashing and authorization-record requirements;
- rollback does not delete the database or touch Suricata/traffic controls.

Live acceptance must additionally record:

- host, principal, repository commit, and clean-tree state;
- service and timer definitions before and after deployment;
- database and directory modes and ownership;
- source schema, accepted/duplicate/rejected counts, event range, row count, and bytes;
- deduplication across two consecutive runs;
- pruning fixtures or a non-production temporary database test;
- absence of listeners and public files;
- unchanged Suricata service/configuration and unchanged traffic-control flags;
- rollback verification;
- protected evidence location.

## Deployment gate

This phase does not include runtime code, systemd units, installer execution, database creation, API routes, authentication changes, or live activation.

Implementation may begin only from a focused branch after exact-head CI and design review. Edge1 activation remains a separate conditional operation requiring an authenticated host path, rollback, immediate verification, and protected terminal evidence.

## Rejected alternatives

- Retaining raw `eve.json`: rejected because it expands privacy and payload risk.
- Reusing the public static endpoint for history: rejected because it exposes a queryable security archive.
- Browser local storage: rejected because freshness, lifecycle, and access cannot be centrally controlled.
- Unbounded SQLite growth: rejected because disk exhaustion can impair unrelated Edge1 services.
- Automatic off-host backup: deferred until destination, encryption, custody, restore, and retention requirements are approved.
- Automatic legal holds: rejected because preservation scope and authority must be explicit.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, Fail2ban jail/action, routing, proxying, IDS rule, reputation list, authentication boundary, certificate, listener, public endpoint, or production traffic is changed by this design.
