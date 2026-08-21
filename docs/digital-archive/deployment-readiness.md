# WW.CX Digital Archive deployment readiness

Tracking: #496
Date: 2026-08-21

## Ready now

- Open Library account exists and is usable.
- Internet Archive account exists and appears verified.
- Zotero account exists; user reports verification complete, but a fresh authenticated browser session is required before API-key setup can be confirmed.
- Omeka S, Paperless-ngx, and ArchiveBox require self-hosted deployment rather than vendor account creation.
- GitHub repository write access is available for architecture, runbooks, adapters, validation, and deployment definitions.

## Infrastructure observations

### Edge1 services

Active relevant foundations include:

- Apache
- HAProxy
- PostgreSQL 15
- MariaDB 10.11
- Redis
- Project Big Bird gateway
- Edge1 Operations API
- Edge1 Operator MCP

### Capacity

Observed root filesystem usage was approximately 63%, with about 29.7 GiB available. This is sufficient for code/configuration and a bounded application working set, but not an approved long-term bulk archive allocation.

### Big Bird connector health

The Big Bird gateway itself reports healthy private-library indexing and integrity. However, the Edge1 connector lifecycle and maintenance services are failed. Diagnose these before making the archive stack depend on their lifecycle management.

### Repository state discrepancy

The bounded Edge1 git-state endpoint reported detached HEAD:

`d326d4546abefa695a293266342a5c1075f010e2`

GitHub `main` at planning time was:

`eccaf13773542259edd897476404fc6355ba8ea7`

Do not deploy archive definitions from the current Edge1 checkout until the purpose of the detached checkout is understood and the intended deployment source is verified.

### Container runtime

Docker/Compose availability has not been verified. Paperless-ngx documentation recommends Docker for most deployments, but the deployment method must be selected based on verified Edge1 capability rather than assumed.

## Next executable checks

These checks require a write-capable or shell-capable Edge1 operator path, not the current bounded read-only connector:

1. Determine whether Docker Engine and Docker Compose are installed and intentionally managed.
2. Inspect the failed Big Bird connector service logs and unit definitions.
3. Identify why the Edge1 repository is detached and reconcile it safely with the intended deployment source.
4. Inventory intended durable archive storage and backup destinations.
5. Verify free ports for private archive services before assigning them.

## Proposed private service boundaries

No public listener should be created during initial deployment.

Suggested logical allocations, subject to live port verification:

- Paperless-ngx: loopback-only application endpoint
- ArchiveBox: loopback-only application endpoint
- Omeka S: Apache/loopback-backed private virtual host or private path

Exact ports and hostnames are deliberately not committed until verified against the live listener inventory and deployment model.

## External adapter credential boundary

Open Library read/search APIs can be implemented without storing a private API credential for ordinary public metadata queries.

Zotero requires a deliberately scoped API key for private library access. The key must be created through the authenticated Zotero account and stored outside Git.

Internet Archive public metadata and Wayback discovery should begin without private credentials. Any later upload/write capability is a separate authorization and credential scope.

## Deployment rule

Do not combine architecture implementation, credential setup, public exposure, bulk ingestion, and migration into one change. Use staged, independently testable phases with reversible changes and explicit acceptance evidence.
