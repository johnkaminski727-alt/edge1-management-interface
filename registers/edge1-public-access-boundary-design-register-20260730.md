# Edge1 Public Access Boundary Design Register

Date: 2026-07-30  
Classification: internal, sanitized design  
System: `edge1.ww.cx` / WW.CX Operations Center  
Repository state: merged through PR #130 as `6e0bbb9d38cd2b89a5ba59ced1534a93ba3aa2eb`

## Trigger and decision

The accepted `edge1.ww.cx/edge1-status/` tree combines public-facing status pages with detailed operational files. Repository review concluded that this mixed tree should not remain unchanged as the long-term access boundary.

Target:

1. a minimized public landing page and allowlist-only aggregate status feed;
2. a separately authenticated, fail-closed detailed operations surface.

No live access, proxy, authentication, certificate, DNS, listener, or published-file change was authorized or performed.

## Evidence reviewed

| Evidence | Verified fact |
| --- | --- |
| `registers/edge1-status-domain-acceptance-20260729.md` | Real-domain HTTPS pages and detailed JSON feeds were accepted; access-control boundaries were unchanged by acceptance |
| `deploy/operations-center/publish.sh` | Operations Center HTML is installed mode `0644` under `/var/www/edge1-status` |
| `src/web/operations-center/index.html` | Public page fetches security, wallet, mining, inventory, network, change, automation, incident, communications, carrier, and report data |
| `tools/operations/validate-operations-center.sh` | Numerous detailed JSON artifacts and reports are expected under the same web root |
| representative operations exporters | Host, service, topology, Git, timer, incident, communications, carrier, and report detail is emitted beneath the web root |

Repository evidence does not prove the complete live Apache authorization, CORS, directory-listing, alias, or HTTP-security-header state. Those remain Phase 0 live checks.

## Accepted design assets

| Asset | Purpose | Repository state |
| --- | --- | --- |
| `config/security/edge1-public-access-boundary-policy.json` | Disabled route, field, rollout, rollback, and acceptance contract | Merged; disabled |
| `schemas/wwcx-edge1-public-access-boundary-policy-v1.schema.json` | Contract constraints | Merged |
| `docs/security/edge1-public-access-boundary-design-20260730.md` | Evidence, classification, target architecture, staging, rollback, and acceptance design | Merged |
| `tests/validate_edge1_public_access_boundary_design.py` | Static scope and safety validation | Merged and passed |

## Information classification

| Class | Examples | Target treatment |
| --- | --- | --- |
| Public minimized summary | aggregate state, bounded count, coarse freshness, maintenance notice | Public allowlist only |
| Restricted security | detailed alerts, endpoints, ports, rules, flows, correlation context | Authenticated or unpublished |
| Restricted topology | host, kernel, services, interfaces, routes, WireGuard, resolver | Authenticated or unpublished |
| Restricted change management | branch, commit, dirty state, commit messages | Authenticated or unpublished |
| Restricted operations | timer names, schedules, recommendations, subsystem details | Authenticated or unpublished |
| Restricted incidents | incident IDs, details, recommendations, history | Authenticated or unpublished |
| Restricted communications | telephony, messaging, numbering, carrier passthrough | Authenticated or unpublished |
| Restricted financial operations | wallet and mining detail | Authenticated or unpublished |
| Restricted evidence | generated reports, filenames, evidence paths | Authenticated or unpublished |

## Target route model

Public design:

```text
/edge1-status/
/edge1-status/public/status.json
```

Future restricted placeholder:

```text
/edge1-ops/
```

The public JSON must be produced from an explicit allowlist, not by redacting arbitrary detailed feeds. Browser authentication and routing require separate exact authorization. Proposed scopes are `edge1.status.detail.read` and, separately, `security.suricata.history.read`.

## Public prohibitions and server controls

Public output excludes host/service/runtime, Git, topology, endpoint/port, rule/flow/event, incident, report/evidence, communications, wallet, mining, and raw error detail.

Future dynamic status requires server-side `Cache-Control: no-store, max-age=0`. Future public HTML requires restrictive CSP, no-referrer, and nosniff headers. Wildcard CORS and directory listing are prohibited.

## Staging boundary

| Phase | Allowed work | Production change |
| --- | --- | --- |
| 0 | Read-only route/header/filesystem inventory | None |
| 1 | Build minimized exporter/page without routing | None |
| 2 | Stage authenticated surface under separate authorization | Conditional |
| 3 | Public cutover | Exact authorization required |
| 4 | Remove detailed public artifacts | Exact authorization required |

## Validation and merge

Exact design head: `24eacfa1388b9c3b9bafb1c8f880af1da3355aea`

| Validation | State |
| --- | --- |
| Accepted domain and repository publication paths inspected | Passed |
| Detailed feed content classes inspected | Passed |
| Mixed-boundary conclusion | Passed |
| Disabled policy, schema, route and forbidden-field contract | Passed |
| Staged rollout and rollback | Passed |
| `Validate repository` run 618 | Success |
| `Edge1 Operator Validation` run 450 | Success |
| Zero commits behind `main` before merge | Confirmed |
| Unresolved review threads | None |
| PR #130 | Merged as `6e0bbb9d38cd2b89a5ba59ced1534a93ba3aa2eb` |
| Live Apache/header/auth inventory | Not performed; no Edge1 shell |
| Runtime/public implementation | Not started |
| Public/authentication change | Not authorized or performed |

## Required implementation evidence

Before any public-boundary change:

- active Apache vhost, alias, auth, directory, and header configuration;
- complete public route and filesystem artifact matrix;
- current anonymous/authorized response matrix;
- current cache, CORS, CSP, referrer, content-type, HSTS, and listing behavior;
- minimized public schema and forbidden-field fixtures;
- authenticated browser design and scope model;
- backup and rollback rehearsal;
- exact-head CI and protected terminal evidence.

## Explicit non-authorization

This design does not authorize proxy, Apache, authentication, certificate, DNS, listener, firewall, publication, removal, service reload, API activation, data deletion, or production cutover.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, Fail2ban, routing, proxy, IDS, reputation list, authentication boundary, certificate, listener, public access, or production traffic is changed.
