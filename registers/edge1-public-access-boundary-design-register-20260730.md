# Edge1 Public Access Boundary Design Register

Date: 2026-07-30  
Classification: internal, sanitized design  
System: `edge1.ww.cx` / WW.CX Operations Center  
Repository state: design branch only

## Trigger

The accepted `edge1.ww.cx/edge1-status/` tree combines public-facing status pages with detailed operational files. The optional review was opened to determine whether the public boundary should remain unchanged.

## Decision

The boundary should not remain unchanged as the long-term design.

The repository should move toward:

1. a minimized public landing page and allowlist-only aggregate status feed;
2. a separately authenticated, fail-closed detailed operations surface.

This register records a design decision only. No live access, proxy, authentication, certificate, DNS, listener, or published-file change is authorized or performed.

## Evidence reviewed

| Evidence | Verified fact |
| --- | --- |
| `registers/edge1-status-domain-acceptance-20260729.md` | Real-domain HTTPS pages and detailed JSON feeds were accepted; access-control boundaries were unchanged by acceptance |
| `deploy/operations-center/publish.sh` | Operations Center HTML is installed mode `0644` under `/var/www/edge1-status` |
| `src/web/operations-center/index.html` | Public page fetches security, wallet, mining, inventory, network, change, automation, incident, communications, carrier, and report data |
| `tools/operations/validate-operations-center.sh` | Numerous detailed JSON artifacts and reports are expected under the same web root |
| `server/operations-inventory-exporter.py` | Host, kernel, Python, modules, and running services are published |
| `server/operations-network-exporter.py` | Interfaces, routes, WireGuard output, and resolver output are published |
| `server/operations-version-exporter.py` | Branch, commit, and dirty state are published |
| `server/operations-changes-exporter.py` | Recent commit hashes/messages and worktree state are published |
| `server/operations-automation-health-exporter.py` | Timer names, states, and next-run values are published |
| incident exporters | Active incident detail and complete incident state history are published |
| communications/carrier exporters | Loopback service responses are passed through into public-root files |
| report exporters | HTML, JSON, PDF, and report index artifacts are generated under the public root |

Repository evidence does not prove the complete live Apache authorization, CORS, directory-listing, or HTTP-security-header state. Those are required Phase 0 live checks.

## Registered design assets

| Asset | Purpose | State |
| --- | --- | --- |
| `config/security/edge1-public-access-boundary-policy.json` | Disabled route, field, rollout, rollback, and acceptance contract | Designed; disabled |
| `schemas/wwcx-edge1-public-access-boundary-policy-v1.schema.json` | Contract constraints | Designed |
| `docs/security/edge1-public-access-boundary-design-20260730.md` | Evidence, classification, target architecture, staging, rollback, and acceptance design | Designed |
| `tests/validate_edge1_public_access_boundary_design.py` | Static scope and safety validation | Designed |

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

### Public

```text
/edge1-status/
/edge1-status/public/status.json
```

The public JSON must be produced from an explicit allowlist, not by redacting arbitrary detailed feeds.

### Future restricted

```text
/edge1-ops/
```

The path is a design placeholder. Browser authentication and routing require a separate exact authorization. Detailed API access should use narrowly scoped authorization such as `edge1.status.detail.read`; future Suricata history remains separately scoped as `security.suricata.history.read`.

## Public data prohibitions

Public output must exclude:

- host, kernel, runtime, module, service, timer, and schedule names;
- Git branch, commit, dirty state, hashes, and messages;
- interfaces, routes, WireGuard, resolver detail, addresses, and ports;
- rule, flow, event, signature, and incident identifiers;
- incident narratives, recommendations, and history;
- report filenames, evidence paths, and raw errors;
- wallet, mining, telephony, messaging, numbering, and carrier detail.

## Header and browser boundary

Future dynamic status must use server-side `Cache-Control: no-store, max-age=0`. Browser `fetch(..., {cache: "no-store"})` alone is not acceptance evidence.

Future public HTML should have a restrictive CSP, `Referrer-Policy: no-referrer`, and `X-Content-Type-Options: nosniff`. Wildcard CORS and directory listing are prohibited.

## Staging boundary

| Phase | Allowed design activity | Production change |
| --- | --- | --- |
| 0 | Read-only route/header/filesystem inventory | None |
| 1 | Build minimized exporter/page without routing | None |
| 2 | Stage authenticated surface under separate authorization | Conditional |
| 3 | Public cutover | Exact authorization required |
| 4 | Remove detailed public artifacts | Exact authorization required |

## Validation state

| Validation | State |
| --- | --- |
| Accepted domain and repository publication paths inspected | Passed |
| Detailed feed content classes inspected | Passed |
| Mixed-boundary conclusion recorded | Passed |
| Disabled policy and schema | Defined |
| Public allowlist and forbidden-field contract | Defined |
| Staged rollout and rollback | Defined |
| Static repository validation | Pending exact-head CI |
| Live Apache/header/auth inventory | Not performed; no Edge1 shell |
| Runtime implementation | Not started |
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
