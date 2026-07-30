# Edge1 Public Access Boundary Design

Date: 2026-07-30  
System: `edge1.ww.cx` / WW.CX Operations Center  
Status: repository design only; no access change authorized or deployed

## Decision

The current `edge1.ww.cx/edge1-status/` tree should not remain unchanged as the long-term access boundary.

Repository evidence shows that one HTTPS tree combines a public-facing status dashboard with detailed operational artifacts containing host inventory, running service names, kernel and runtime versions, interfaces and routes, WireGuard and resolver output, Git branch/commit/worktree state, timer names and schedules, incident detail/history, communications subsystem responses, and generated operations reports.

The recommended target is a split boundary:

1. a minimized public status surface containing bounded aggregate states, counts, freshness, and maintenance notices only;
2. a separately authenticated, fail-closed operations surface for detailed infrastructure, security, incident, communications, financial, and evidence data.

This document defines that target but makes no Apache, proxy, authentication, certificate, listener, DNS, filesystem-publication, or traffic change.

## Evidence basis

The accepted domain record proves that:

- `edge1.ww.cx` serves the Operations Center and security modules over HTTPS;
- HTTP redirects to HTTPS;
- the Operations Center, Security Operations, Security Correlation, and Network Defense pages returned successfully through the real domain;
- detailed Security Operations, Security Correlation, and Network Defense JSON feeds loaded through the same domain;
- the acceptance run did not alter authentication or access-control boundaries.

The repository publisher installs the Operations Center page to:

```text
/var/www/edge1-status/index.html
```

The dashboard performs browser `no-store` fetches for numerous JSON documents under the same static root, including inventory, network posture, repository changes, automation, incidents, communications, carrier, wallet, mining, and reports.

Repository evidence does not establish the complete current Apache authorization rules, CORS policy, directory-index policy, or response security headers. Those items remain mandatory live preflight checks before any boundary implementation.

## Current mixed information classes

### Host and topology detail

`operations-inventory.json` includes:

- hostname;
- kernel and Python versions;
- module inventory;
- up to 100 running service lines.

`operations-network.json` includes:

- interface and address output;
- routes;
- WireGuard output;
- resolver status.

These are restricted topology data, not public status data.

### Change-management detail

`operations-version.json` and `operations-changes.json` include:

- branch and commit identifiers;
- dirty/clean state;
- recent commit hashes and messages.

These belong to authenticated operations and deployment evidence.

### Automation and incident detail

`operations-automation.json` publishes timer unit names, states, and next-run values.

`operations-incidents.json` and `operations-incident-history.json` publish component names, incident identifiers, severity, detail, recommendations, timestamps, and state history.

These belong to authenticated operations and incident handling.

### Communications and carrier detail

The telephony, messaging, and carrier exporters pass through responses from loopback services into files under `/var/www/edge1-status`. Those responses may evolve independently of the dashboard and therefore cannot be safely treated as a stable public schema without an explicit minimization layer.

### Security detail

The Security Operations and Correlation modules are sanitized against payload, credential, key, and raw-log disclosure, but still contain investigative endpoint, port, rule, flow, event, timing, and cross-source context. Sanitized does not mean appropriate for unauthenticated historical or investigative exposure.

Network Defense is more heavily aggregated, but its detailed source records, component metrics, and source names should remain an authenticated view. A separate public summary may derive only approved aggregate fields.

### Reports and financial operations

The reports directory stores generated HTML, JSON, and PDF operations reports that embed health, changes, automation, and correlation records. Bitcoin wallet and mining modules also expose operational and potentially financially sensitive state. These are restricted surfaces.

## Machine-readable contract

Policy:

```text
config/security/edge1-public-access-boundary-policy.json
```

Schema:

```text
schemas/wwcx-edge1-public-access-boundary-policy-v1.schema.json
```

Contract:

```text
wwcx.edge1-public-access-boundary-policy.v1
```

The policy is `design_only`, `enabled: false`, and `deployment_authorized: false`.

## Target public contract

The future public root remains conceptually:

```text
https://edge1.ww.cx/edge1-status/
```

It should contain only:

- a static minimized landing page;
- a new aggregate status document such as `/edge1-status/public/status.json`;
- bounded state labels;
- bounded counts;
- coarse freshness buckets;
- maintenance notices;
- explicit read-only and no-traffic-change flags.

The public contract must not include:

- host, kernel, runtime, service, timer, branch, commit, or worktree detail;
- interface, route, WireGuard, resolver, IP address, endpoint, or port detail;
- flow, event, rule, or incident identifiers;
- incident narratives, recommendations, or history;
- report filenames or evidence paths;
- wallet, mining, telephony, messaging, numbering, or carrier detail;
- raw errors or passthrough responses.

The public summary must be produced by an explicit allowlist exporter. It must not copy and then redact arbitrary operational JSON.

## Target authenticated contract

A future authenticated root is represented in the policy as:

```text
/edge1-ops/
```

The exact browser-authentication mechanism is intentionally undecided. It requires a separate design because the existing Edge1 Operations API HMAC model is suitable for typed API clients but is not automatically a browser-session design.

Future restricted access must:

- fail closed;
- have no anonymous fallback;
- audit successful and denied reads;
- apply rate limits;
- use narrowly scoped authorization;
- separate detailed status scope `edge1.status.detail.read` from future Suricata-history scope `security.suricata.history.read`;
- return 401/403 for authorization failures or 404 when an artifact is deliberately unpublished.

No authentication implementation is authorized by this phase.

## Route classification

The machine-readable policy records the complete reviewed route classes. The principal decisions are:

- Operations landing page: replace its data dependencies before it remains the public landing page;
- Security Operations and Correlation: authenticated or unpublished;
- detailed Network Defense: authenticated, with a separate minimized public summary;
- Bitcoin and mining modules: authenticated or unpublished;
- inventory, network, version, changes, automation, incidents, incident history, telephony, messaging, carrier, and reports: authenticated or unpublished;
- existing detailed JSON feeds: never used directly as the future public contract.

This classification is based on repository contents. A live implementation must first generate a complete Apache route/alias matrix because other filesystem artifacts or aliases may exist outside the repository evidence reviewed here.

## Cache and browser policy

Browser-side `fetch(..., {cache: "no-store"})` is useful but does not replace server response headers.

Future dynamic public and restricted status responses should require:

```text
Cache-Control: no-store, max-age=0
Pragma: no-cache
Expires: 0
```

Future HTML should receive, at minimum:

```text
Content-Security-Policy: default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'
Referrer-Policy: no-referrer
X-Content-Type-Options: nosniff
```

Wildcard CORS and directory listing are prohibited. Header changes belong to the separately authorized implementation phase.

## Staged implementation sequence

### Phase 0 — read-only live inventory

Capture:

- active Apache virtual-host and alias configuration;
- filesystem tree, ownership, modes, symlinks, and index behavior under the status root;
- unauthenticated and authorized response matrix;
- redirects, CORS, cache, CSP, referrer, content-type, HSTS, and directory-listing behavior;
- certificate identity and listener state;
- exact existing routes not represented in the repository.

No service reload or configuration change occurs in Phase 0.

### Phase 1 — build minimized outputs without routing

On a focused repository branch:

- define the public summary schema;
- implement an allowlist-only summary exporter;
- add sensitive-field tests and fixtures;
- build a static minimized landing page that consumes only the new summary;
- do not publish or route it live.

### Phase 2 — stage authenticated operations surface

Under separate authentication authorization:

- choose the browser identity/session mechanism;
- stage the restricted route on a non-public or otherwise bounded test path;
- verify fail-closed behavior, audit logs, rate limits, and scope enforcement;
- do not cut over the public tree.

### Phase 3 — public cutover

Requires explicit authorization for the exact proxy/public-access change:

- back up active vhost and published files;
- publish the minimized public page and summary;
- route restricted operations through the approved authenticated boundary;
- verify the full response matrix immediately.

### Phase 4 — remove detailed public artifacts

Requires explicit authorization because it changes live availability and may delete published copies:

- remove public aliases or published copies only after the authenticated path is accepted;
- preserve authoritative operational sources and evidence;
- verify no broken dashboard dependencies remain.

## Acceptance criteria

A future live boundary change is accepted only when protected evidence proves:

- the public route matrix contains only the public allowlist;
- public responses pass a recursive forbidden-field scan;
- restricted routes fail closed without authorization;
- an authorized principal can access only the permitted restricted scope;
- no directory listing or wildcard CORS exists;
- dynamic status has server-side no-store headers;
- the public page depends only on minimized public output;
- no new listener, DNS, certificate, firewall, resolver, IDS, or traffic-control change occurred;
- TLS identity and port 80-to-443 redirect remain correct;
- rollback restores the previous vhost and files;
- operational source data is preserved.

A successful HTTP status alone is insufficient.

## Rollback

Rollback must restore:

- the previous Apache virtual-host and alias files from a timestamped backup;
- the previous published static files;
- the previous route behavior after syntax validation and controlled reload.

Rollback must preserve operational source data. Deletion of operational records or evidence is not part of rollback. No DNS, certificate, or firewall rollback should be required because the recommended boundary change does not require those systems.

## Explicit non-authorization

This design does not authorize:

- Apache, proxy, alias, or authentication changes;
- certificate issuance or replacement;
- DNS changes;
- listener or firewall changes;
- publication or removal of files under `/var/www`;
- API scope activation;
- service reload or restart;
- deletion of reports, status files, incidents, or evidence;
- any production cutover.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, Fail2ban, routing, proxying, IDS rules, reputation lists, authentication boundary, certificate, listener, public access, or production traffic is changed by this design.
