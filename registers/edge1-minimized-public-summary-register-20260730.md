# Minimized Edge1 Public Summary Register

Date: 2026-07-30  
Classification: internal, sanitized implementation record  
System: `edge1.ww.cx` / WW.CX Operations Center  
Repository state: merged through PR #132 as `25359040ba07a3b7bf513f95b32ce24f6be480f2`; route correction merged through PR #140 as `4fc5d765805b86be8ddee58f08c2676116517cbb`; CSP correction in validation; not deployed

## Trigger

The accepted public-boundary design concluded that the current mixed `/edge1-status/` tree should not remain unchanged. Phase 1 implemented a minimized summary in the repository without routing or publication.

Follow-up review found and corrected two pre-publication contract defects:

1. the accepted policy route `/edge1-status/public/status.json` did not match the original landing-page relative fetch;
2. the page used an inline stylesheet that would be blocked by the approved CSP.

The canonical route now matches the policy, and the stylesheet is external so the exact strict CSP can be enforced without `unsafe-inline`.

## Accepted assets

| Asset | Purpose | Repository state |
| --- | --- | --- |
| `server/edge1_public_status_exporter.py` | Allowlist-only summary builder with explicit input paths and build-scoped `public/status.json` output | Merged through PR #140 |
| `schemas/wwcx-edge1-public-status-v1.schema.json` | Exact minimized document contract | Merged |
| `src/web/public-status/index.html` | Non-routed static minimized landing page with exact approved CSP | Merged; CSP correction in validation |
| `src/web/public-status/app.js` | Renderer that fetches only `./public/status.json` | Merged through PR #140 |
| `src/web/public-status/style.css` | Same-origin external presentation with no inline-style requirement | CSP correction in validation |
| hostile JSON fixtures | Prove detailed source values do not propagate | Merged |
| `tests/validate_edge1_public_status.py` | Privacy, bounds, failure, output, page, route, CSP, and no-deployment validation | CSP correction in validation |
| `docs/security/edge1-minimized-public-summary-20260730.md` | Architecture and deployment boundary | CSP correction in validation |

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

Fixed categories are `security`, `network_defense`, and `operations`. Each category includes only state, bounded count, and coarse freshness.

## Source reduction and bounds

| Input | Read values | Explicitly ignored |
| --- | --- | --- |
| Security Operations | health state, recent-alert count, generation time | alert contents, engine detail, service names, addresses, ports, IDs, errors |
| Network Defense | overall state, available-source count, generation time | source records, metrics, topology, names, counters, resolver/WireGuard detail |
| Operations Health | overall state, check count, generation time | check names/details, recommendations, host, services, Git, incidents, reports |

| Value | Bound |
| --- | --- |
| Security count | 0–999 |
| Network source count | 0–99 |
| Operations check count | 0–99 |
| Maintenance notice | 160 characters |
| Fresh | at most 5 minutes |
| Aging | more than 5 and at most 15 minutes |
| Stale | more than 15 minutes |

Source objects and arbitrary strings are never copied into output.

## Build, route, and CSP boundary

Default output:

```text
build/edge1-public-status/public/status.json
```

Canonical future public route:

```text
/edge1-status/public/status.json
```

Approved CSP:

```text
default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'
```

All three input paths are required. The exporter contains no `/var/www`, Apache, systemd, command-execution, or network-access path.

The page consumes only `./public/status.json`, loads `app.js` and `style.css` from the same origin, has no inline script or style dependency, requests no-store, omits credentials, suppresses referrer data, references no detailed feeds, and links to no restricted surface. It is not connected to a deploy script or public route.

## Hostile fixture boundary

Fixtures include host/kernel, service, addresses, ports, alert signatures/IDs, routes, WireGuard, resolver, Git, incident, report, error, and recommendation detail. Validation proves none of those values or forbidden keys appears in output.

## Validation and merge

Exact implementation head: `d431bd358969ed1db4902f1bc84f02bea1ce7cd1`

| Validation | State |
| --- | --- |
| Exact field allowlist | Passed |
| Policy/schema alignment | Passed |
| Hostile-value exclusion | Passed |
| Count/notice/freshness bounds | Passed |
| Missing/stale degradation | Passed |
| Atomic build-scoped output | Passed |
| No command/network/live path | Passed |
| Page minimized-feed-only | Passed |
| No deployment/service assets | Passed |
| `Validate repository` run 622 | Success |
| `Edge1 Operator Validation` run 454 | Success |
| Zero commits behind `main` before merge | Confirmed |
| Unresolved review threads | None |
| PR #132 | Merged as `25359040ba07a3b7bf513f95b32ce24f6be480f2` |
| Canonical route correction PR #140 | Merged as `4fc5d765805b86be8ddee58f08c2676116517cbb` |
| Strict CSP agreement | Correction implemented; exact-head validation pending |
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
