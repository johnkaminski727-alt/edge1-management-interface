# Protected Suricata Retention Runtime Register

Date: 2026-07-30  
Classification: internal security operations; no alert data  
System: Edge1 / WW.CX Security Operations  
State: repository implementation; disabled and not deployed

## Objective

Implement the bounded runtime defined by the accepted protected-retention design without activating it on Edge1, creating a production database, changing Suricata, or exposing a listener or public route.

## Implemented assets

| Asset | Purpose | Runtime boundary |
| --- | --- | --- |
| `server/suricata_protected_retention.py` | Validate, deduplicate, retain, prune, and query sanitized alerts | Reads only the sanitized collector snapshot; no raw EVE, network, subprocess, or control-plane access |
| `deploy/systemd/wwcx-suricata-protected-retention.service` | Hardened root-only oneshot | AF_UNIX only, empty capabilities, strict filesystem allowlist |
| `deploy/systemd/wwcx-suricata-protected-retention.timer` | Proposed 120-second schedule | Committed only; not installed or enabled |
| `tests/test_suricata_protected_retention.py` | Functional, privacy, capacity, query, and systemd validation | Temporary files and SQLite databases only |

## Safety and activation gates

The authoritative committed policy remains:

- `status: design_only`;
- `enabled: false`;
- `activation_requires_explicit_authorization: true`;
- `acceptance.deployment_authorized: false`.

The runtime requires both `enabled: true` and `deployment_authorized: true`. Otherwise it emits a root-only `disabled` status and does not create the history database.

No installer or activation script is included in this phase. No systemd unit is installed, no daemon reload is performed, no timer is enabled, and no Edge1 host mutation is claimed.

## Ingestion boundary

- source: `/var/lib/bigbird/operations-center/latest.json` only;
- required schema: `wwcx.suricata-source-alert.v1`;
- maximum 100 alerts per run;
- unknown fields and nested values rejected;
- approved fields revalidated and bounded;
- deterministic SHA-256 event key using policy-defined canonical fields;
- SQLite primary-key deduplication;
- no raw EVE path or raw log access.

## Storage boundary

- root-only directory mode `0700`;
- database and aggregate status mode `0600`;
- 30-day target;
- 100,000 event hard limit;
- 256 MiB SQLite page ceiling;
- pruning by age, count, and page headroom;
- bounded incremental reclamation only;
- database preserved by default.

## Query boundary

The local CLI opens the database read-only and enforces:

- default 24-hour window and 100 rows;
- maximum seven days and 500 rows;
- root-only file permissions;
- no HTTP, TCP, UDP, browser, or public-static history surface.

## Validation intent

The test suite covers disabled fail-closed behavior, two-run deduplication, schema rejection, unknown-field rejection, stable canonical hashing, time/count pruning, root-only modes, bounded read-only queries, status truthfulness, systemd hardening, and absence of raw-EVE or network-server paths.

Local clone validation could not run in the authoring container because DNS resolution for `github.com` was unavailable. Exact-head GitHub Actions is therefore required before merge.

## Explicit non-authorization

This repository phase does not authorize database creation on Edge1, installation or enablement of the new units, daemon reload, production ingestion, incident export, data deletion, Suricata restart/reload, authentication change, listener, public route, `/var/www` write, DNS/firewall change, or traffic mutation.
