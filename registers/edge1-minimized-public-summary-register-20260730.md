# Minimized Edge1 Public Summary Register

Date: 2026-07-30  
Classification: internal, sanitized implementation record  
System: `edge1.ww.cx` / WW.CX Operations Center  
Repository state: feature branch only; not deployed

## Trigger

The accepted public-boundary design concluded that the current mixed `/edge1-status/` tree should not remain unchanged. Phase 1 permits a minimized summary implementation in the repository without routing or publication.

## Implemented assets

| Asset | Purpose | State |
| --- | --- | --- |
| `server/edge1_public_status_exporter.py` | Allowlist-only summary builder with explicit input paths and build-scoped output | Implemented on feature branch |
| `schemas/wwcx-edge1-public-status-v1.schema.json` | Exact minimized document contract | Implemented |
| `src/web/public-status/index.html` | Non-routed static minimized landing page | Implemented |
| `src/web/public-status/app.js` | Renderer that fetches only `./status.json` | Implemented |
| hostile JSON fixtures | Prove detailed source values do not propagate | Implemented |
| `tests/validate_edge1_public_status.py` | Privacy, bounds, failure, output, page, and no-deployment validation | Implemented |
| `docs/security/edge1-minimized-public-summary-20260730.md` | Architecture and deployment boundary | Implemented |

## Public contract

Schema identifier:

```text
wwcx.edge1-public-status.v1
```

Exact top-level fields:

- `schema_version`;
- `generated_at`;
- `overall_state`;
- `component_category`;
- `maintenance_notice`;
- `read_only`;
- `traffic_controls_changed`.

Fixed categories:

- `security`;
- `network_defense`;
- `operations`.

Each category includes only state, bounded count, and coarse freshness.

## Source reduction

| Input | Read values | Explicitly ignored |
| --- | --- | --- |
| Security Operations | health state, recent-alert count, generation time | alert contents, engine detail, service names, addresses, ports, IDs, errors |
| Network Defense | overall state, available-source count, generation time | source records, metrics, topology, names, counters, resolver/WireGuard detail |
| Operations Health | overall state, check count, generation time | check names/details, recommendations, host, services, Git, incidents, reports |

Source objects and arbitrary strings are never copied into output.

## Bounds

| Value | Bound |
| --- | --- |
| Security count | 0–999 |
| Network source count | 0–99 |
| Operations check count | 0–99 |
| Maintenance notice | 160 characters |
| Fresh | at most 5 minutes |
| Aging | more than 5 and at most 15 minutes |
| Stale | more than 15 minutes |

## Default output boundary

```text
build/edge1-public-status/status.json
```

All three input paths are required CLI arguments. The exporter contains no `/var/www`, Apache, systemd, command-execution, or network-access path.

## Page boundary

The page and renderer:

- consume only `./status.json`;
- request no-store, omit credentials, and suppress referrer data;
- do not reference existing detailed feeds;
- do not link to restricted surfaces;
- are not connected to a deploy script or public route.

## Hostile fixture boundary

The fixtures include host/kernel, service, addresses, ports, alert signatures/IDs, routes, WireGuard, resolver, Git, incident, report, error, and recommendation detail. Validation requires that none of those values or forbidden keys appear in the result.

## Validation state

| Validation | State |
| --- | --- |
| Exact field allowlist | Pending exact-head CI |
| Policy/schema alignment | Pending exact-head CI |
| Hostile-value exclusion | Pending exact-head CI |
| Count/notice/freshness bounds | Pending exact-head CI |
| Missing/stale degradation | Pending exact-head CI |
| Atomic build-scoped output | Pending exact-head CI |
| No command/network/live path | Pending exact-head CI |
| Page minimized-feed-only | Pending exact-head CI |
| No deployment/service assets | Pending exact-head CI |
| Edge1 publication | Not authorized or performed |
| Public cutover | Not authorized or performed |

## Future live prerequisites

Before publication:

- read-only Apache route, alias, auth, header, CORS, listing, and filesystem inventory;
- server-side no-store/CSP/referrer/nosniff policy;
- output ownership/mode and publication design;
- backup and rollback procedure;
- exact authorization for public route change;
- protected terminal acceptance evidence.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, Fail2ban, routing, proxying, IDS, reputation list, authentication, certificate, listener, public access, `/var/www` publication, deletion, or production traffic is changed.
