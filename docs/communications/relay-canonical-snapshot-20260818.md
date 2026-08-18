# Relay canonical Communications snapshot

Date: 2026-08-18

## Purpose

Expose read-only NNTP/Relay metadata to the WW.CX Communications workspace without copying native article bodies or replacing the authoritative Relay database.

The authoritative source remains `/var/lib/wwcx-comms/comms.sqlite3`. The canonical layer stores references and bounded metadata only under `wwcx.communications-event.v1`.

## Live Edge1 evidence

A read-only Edge1 inspection on 2026-08-18 established:

- `edge1-comms-relay.service` was active;
- the native Relay database contained 168 `articles` rows and 168 `ingest_items` rows;
- every ingest row linked to an existing article and there were zero missing article links;
- all 168 native articles contained bodies, so body exclusion is a material safety requirement;
- the accepted ingest sources were `edge1-repository`, `wwcx-bootstrap`, `eternal.comp.lang.python`, and `eternal.news.admin.peering`;
- a temporary metadata-only candidate of 168 canonical events validated successfully through the Communications workspace `SnapshotStore`;
- the candidate was not attached to the live workspace during that acceptance pass;
- the live workspace remained empty, read-only, and loopback-only.

## Adapter behavior

`server/communications_relay_snapshot.py`:

- opens Relay SQLite in read-only/query-only mode;
- joins native `articles` to authoritative `ingest_items` linkage;
- fails closed if article and ingest counts do not match or a source is unclassified;
- never selects the native `body` column;
- hashes the native author string before emitting an identity reference;
- includes only bounded newsgroup, subject, timestamp, source and native-record identifiers;
- marks `edge1-repository` and `wwcx-bootstrap` as internal and reviewed `eternal.*` sources as inbound;
- preserves `native_record.source=edge1-comms-relay` and `authoritative_native_record=true`;
- keeps `quarantine_release_authorized=false`;
- validates every event through the canonical Communications contract;
- writes the JSONL snapshot by atomic replacement with mode `0640`.

## Runtime refresh design

`wwcx-communications-relay-snapshot.service` is a hardened oneshot service that runs as `wwadmin` with supplementary read access to the `wwcx-comms` group. It can read the native Relay database and write only `/var/lib/wwcx-communications-workspace`.

`wwcx-communications-relay-snapshot.timer` refreshes the snapshot every 15 minutes, matching the established Relay ingestion cadence. The workspace reads its snapshot on each request, so a successful refresh does not require restarting the workspace.

Attaching the persistent snapshot to the workspace remains a separate live activation step through `WWCX_COMMUNICATIONS_EVENT_SNAPSHOT`. That activation must preserve the loopback-only listener, read-only mutation boundary, and rollback path.

## Explicit exclusions

This adapter does not:

- expose article bodies or raw headers;
- expose raw author identities;
- post or ingest NNTP content;
- alter Relay retention or configuration;
- grant AI, send, routing, quarantine-release, or mutation authority;
- create a public listener;
- treat health, audit, or analytics databases as correspondence sources.
