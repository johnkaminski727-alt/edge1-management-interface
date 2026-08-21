# WW.CX Digital Archive architecture

Status: foundation design
Tracking: #496
Date: 2026-08-21

## Purpose

The WW.CX Digital Archive is a federated archival and research layer. It does not replace the authoritative source systems that already hold original records. It adds preservation, classification, citation, curated presentation, cross-system relationships, and a controlled search/orchestration surface for Project Big Bird.

## Authority model

| System | Role | Authority |
| --- | --- | --- |
| ChatGPT Library / Google Drive / Dropbox / other approved source repositories | Original records and evidence | Authoritative where already designated |
| Paperless-ngx | OCR, classification, tagging, retrieval, workflow | Derived/indexing layer |
| ArchiveBox | Captured web evidence and replayable web preservation | Authoritative for the specific capture artifact it creates, not for the live source |
| Omeka S | Curated collections, exhibits, linked descriptive metadata | Curatorial/presentation layer |
| Zotero | Research citations, bibliography, notes, source relationships | Research/provenance layer |
| Open Library | External book/author/edition discovery | External reference source |
| Internet Archive / Wayback Machine | External discovery and historical web/media source | External reference/capture source |
| Airtable Operations Registry | Operational relationships, lifecycle, verification, pointers | Operational metadata layer |
| Project Big Bird | Search, orchestration, validation, controlled automation | Integration layer |

No derived system may silently become authoritative for an existing source record.

## Archive object identity

Every internally tracked archive object should receive a stable identifier with a format such as:

`WWCX-ARC-<YYYY>-<opaque sequence>`

The identifier must remain stable even if filenames, folders, tags, or downstream-system record IDs change.

Minimum metadata:

- stable WW.CX archive ID
- title and normalized title
- object type
- source system
- source record ID
- authoritative location/reference
- SHA-256 when byte content is available
- optional interoperable secondary digest
- original filename and/or source URL
- created/issued date when known
- acquired/captured date
- creator/correspondent/organization relationships
- project/case/matter relationships
- access classification
- retention class
- verification status and verification date
- provenance notes
- duplicate/supersedes relationships
- external identifiers such as ISBN, Open Library ID, Internet Archive identifier, Zotero key, Omeka resource ID, and ArchiveBox snapshot ID

## Storage principle

Application state, metadata, and configuration must be separated from long-term payload storage.

Edge1 currently has enough capacity for application deployment and a bounded working set, but it should not be treated as the long-term bulk archive payload store. Payload storage must be allocated deliberately and backed up independently.

## Security and secret handling

Do not store passwords, API secrets, private keys, authentication tokens, financial credentials, government identifiers, or unnecessary sensitive personal data in Git, Airtable, Omeka descriptive metadata, or other operational indexes.

Connector secrets must live outside Git and be readable only by the service identity that requires them.

All new archive applications should begin private/loopback-only. Public exposure is a later decision after authentication, backup, restore, and access-control acceptance tests pass.

## Integration phases

### Phase A — foundation

1. Reconcile the Edge1 deployment checkout with the repository source of truth before deployment work.
2. Diagnose the failed Big Bird Edge1 connector lifecycle and maintenance services.
3. Verify Docker/Compose availability; do not assume it from documentation.
4. Reserve service ports, paths, database names/schemas, service users, and backup destinations.
5. Establish backup/restore tests, digest policy, retention classes, and secret locations.

### Phase B — external read-only adapters

Implement read-only adapters first for:

- Open Library search, authors, works, editions, ISBN metadata
- Internet Archive metadata and Wayback discovery
- Zotero library metadata and citations

Register them with Big Bird in read-only mode and add deterministic validation fixtures before enabling any write scope.

### Phase C — self-hosted services

Deploy privately:

- Paperless-ngx with PostgreSQL and dedicated media/consume/export paths
- ArchiveBox with a dedicated capture store
- Omeka S with an isolated database and media directory

Create local admin identities using secrets outside the repository. Record only non-secret operational metadata in registries.

### Phase D — interoperability

Cross-link records rather than copying authority:

- Paperless document -> authoritative source record
- Zotero item -> archive object/source citation
- Omeka resource -> curated archive object
- ArchiveBox snapshot -> URL + capture timestamp + digest + archive object
- external Open Library/Internet Archive identifiers -> research/reference relationships

### Phase E — unified search and controlled automation

Expose a unified read-only Big Bird search across:

- existing private library index
- Paperless-ngx
- Zotero
- Omeka S
- ArchiveBox
- Open Library
- Internet Archive

Only after read-only acceptance should staged writes be introduced. Every write workflow must carry source, provenance, digest, duplicate detection, review state, and rollback information.

## Current readiness observations

Read-only Edge1 diagnostics on 2026-08-21 showed:

- Apache, HAProxy, PostgreSQL 15, MariaDB 10.11, and Redis active.
- roughly 29.7 GiB free on the root filesystem at the time of inspection.
- Big Bird gateway healthy with private-library integrity reported OK.
- `bigbird-edge1-connector.service` and `bigbird-edge1-connector-maintenance.service` failed.
- the bounded git-state endpoint reported detached HEAD `d326d4546abefa695a293266342a5c1075f010e2`, while GitHub `main` was `eccaf13773542259edd897476404fc6355ba8ea7`.
- Docker was not visible in the bounded systemd service inventory, so availability is unverified.

These are deployment prerequisites, not reasons to weaken the architecture.

## Acceptance milestone 1

Milestone 1 is complete when:

1. Open Library and Zotero can be queried through validated read-only Big Bird adapters.
2. Internet Archive/Wayback discovery is available through a validated read-only adapter.
3. Paperless-ngx, ArchiveBox, and Omeka S are privately installed and health-checked.
4. backup and restore procedures have been tested for each self-hosted service.
5. source records remain unchanged and authoritative.
6. Big Bird can perform one federated read-only query across the existing private library and the newly integrated archive sources.
