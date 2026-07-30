# Minimized Edge1 Public Summary Handoff

Date: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Authoritative base: `1d995bbc0ec9029c9853d9968470f248eb8b6995`  
Feature branch: `feature/edge1-minimized-public-summary-20260730`

## Verified live baseline

- Security Correlation and Network Defense are live and accepted.
- Suricata drill-down, caching, normalization, and enrichment are live.
- Spamhaus, Fail2ban, and nftables report accepted truthful states.
- DNS remains unstaged and disabled; traffic controls remain unchanged.

## Prior repository decisions

- Freshness phase is repository-complete but not live-activated.
- Protected-retention design is disabled and non-deploying.
- Public boundary design concluded that the current mixed `/edge1-status/` tree should be replaced in a future authorized cutover by a minimized public summary and separately authenticated detail.

## Current implementation

Phase 1 builds the minimized artifacts without routing or publication.

Schema:

```text
wwcx.edge1-public-status.v1
```

Assets:

```text
server/edge1_public_status_exporter.py
schemas/wwcx-edge1-public-status-v1.schema.json
src/web/public-status/index.html
src/web/public-status/app.js
tests/fixtures/edge1_public_status/*.json
tests/validate_edge1_public_status.py
docs/security/edge1-minimized-public-summary-20260730.md
registers/edge1-minimized-public-summary-register-20260730.md
```

## Output

Exact top-level fields:

```text
schema_version
generated_at
overall_state
component_category
maintenance_notice
read_only
traffic_controls_changed
```

Fixed categories:

```text
security
network_defense
operations
```

Each category contains only category, state, bounded count, and freshness bucket.

## Source minimization

- Security: health state, recent-alert count, generation time.
- Network Defense: overall state, available-source count, generation time.
- Operations: overall state, check count, generation time.

No source object, detail, recommendation, error, path, address, port, ID, service, timer, Git, incident, report, communications, wallet, or mining field is copied.

## Bounds

- Security count: 999 maximum.
- Network and Operations counts: 99 maximum.
- Notice: 160 characters maximum.
- Fresh: no older than five minutes.
- Aging: five to fifteen minutes.
- Stale: older than fifteen minutes and represented as attention.

## Publication boundary

- All input paths are required.
- Default output is `build/edge1-public-status/status.json`.
- Exporter has no command execution, network access, `/var/www`, Apache, or systemd path.
- Page fetches only `./status.json`.
- No deploy script, service, timer, alias, route, or public URL activation exists.

## Validation coverage

- exact allowlists and schema/policy alignment;
- hostile source value and forbidden-key exclusion;
- count, notice, freshness, stale, and missing-source behavior;
- atomic mode-0644 build output;
- no command/network/live publication markers;
- page minimized-feed-only and no restricted links;
- no deployment or service assets.

## Pending sequence

1. Open focused PR.
2. Require exact-head `Validate repository` and `Edge1 Operator Validation`.
3. Repair only implementation/test defects.
4. Confirm changed scope contains no deploy, systemd, Apache, auth, or live-publication assets.
5. Confirm zero behind, mergeable, and no unresolved threads.
6. Merge and close repository records.
7. Do not publish until read-only live inventory and exact public-change authorization exist.

## Live evidence gap

No authenticated Edge1 shell is available. Current Apache/auth/header/CORS/listing/alias/filesystem behavior remains unverified.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, Fail2ban, routing, proxying, IDS, reputation list, authentication, certificate, listener, public access, `/var/www` publication, deletion, or production traffic is changed or authorized.
