# Edge1 Public Access Boundary Design Handoff

Date: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Authoritative base: `74323ce0d572806278afe400f3c1e9e244e89d10`  
Design branch: `design/edge1-public-access-boundary-20260730`

## Verified live baseline

- Network Defense and Security Correlation are deployed and accepted.
- Suricata drill-down, last-known-good caching, normalization, and source enrichment are live.
- Spamhaus is `active_verified` and remains the sole enforcement-verified source.
- Fail2ban is `active_observed` with service/socket health and 7 observed jails.
- General nftables aggregate visibility is `ruleset_observed`.
- Network Defense remains `limited`, 8 of 9 sources are available, DNS policy is `not_staged`, DNS enforcement is disabled, and traffic controls remain unchanged.

## Prior repository phases

- Network Defense freshness is closed through PR #127; its live activation remains unclaimed without an Edge1 shell.
- Protected Suricata retention design is closed through PR #129; its policy remains disabled and no runtime exists.

## Current boundary finding

The repository shows a mixed public tree under `/edge1-status/`.

The Operations Center page fetches detailed security, wallet, mining, health, automation, version, inventory, network, telephony, messaging, carrier, incident, incident-history, and report feeds. Representative exporters place host, service, kernel, route, WireGuard, resolver, Git, schedule, incident, passthrough subsystem, and generated report detail beneath `/var/www/edge1-status`.

Decision: the unchanged mixed boundary is not the safest long-term design.

## Target design

### Public

```text
/edge1-status/
/edge1-status/public/status.json
```

The public surface contains a static minimized landing page and an explicit allowlist-only summary. Allowed information is limited to aggregate state, bounded counts, coarse freshness, maintenance notices, and read-only/no-traffic-change flags.

### Restricted

A future authenticated surface is represented as:

```text
/edge1-ops/
```

Detailed security, topology, change, automation, incident, communications, financial, and report/evidence data is restricted. The exact browser-authentication mechanism and proxy routing are separate design and authorization work.

Proposed scopes:

```text
edge1.status.detail.read
security.suricata.history.read
```

No anonymous fallback is allowed.

## Design assets

```text
config/security/edge1-public-access-boundary-policy.json
schemas/wwcx-edge1-public-access-boundary-policy-v1.schema.json
docs/security/edge1-public-access-boundary-design-20260730.md
registers/edge1-public-access-boundary-design-register-20260730.md
tests/validate_edge1_public_access_boundary_design.py
```

Contract:

```text
wwcx.edge1-public-access-boundary-policy.v1
```

The policy is `design_only`, `enabled: false`, and `deployment_authorized: false`.

## Required server-side controls for a future implementation

- public allowlist and recursive forbidden-field scan;
- restricted routes fail closed;
- audited and rate-limited authorized reads;
- `Cache-Control: no-store, max-age=0` for dynamic status;
- restrictive CSP, no-referrer, and nosniff headers;
- no wildcard CORS;
- no directory listing;
- no new listener;
- unchanged TLS identity and HTTP-to-HTTPS redirect;
- rollback restoring previous vhost/aliases and static files while preserving operational data.

## Staged sequence

1. read-only live Apache/header/filesystem/route inventory;
2. build minimized output without routing;
3. stage authenticated surface under separate authorization;
4. public cutover under exact authorization;
5. remove detailed public artifacts only after authenticated acceptance and separate authorization.

## Validation status

Completed:

- accepted domain record and publication path review;
- browser dependency inventory;
- representative detailed exporter review;
- route and information classification;
- disabled policy and schema;
- static design validator;
- design, register, backlog, state, and handoff updates.

Pending:

- exact-head `Validate repository`;
- exact-head `Edge1 Operator Validation`;
- final scope, mergeability, and review-thread checks;
- merge and authoritative closeout.

## Live evidence gap

No authenticated Edge1 shell is available. The repository does not establish the complete current Apache authorization, alias, CORS, directory-listing, response-header, or extra-filesystem route state. Do not claim those controls are present or absent until a read-only live inventory is captured.

## Explicitly not implemented

- minimized exporter or landing page;
- authenticated operations UI or browser session;
- proxy/vhost/alias changes;
- security headers;
- API scope activation;
- publication/removal under `/var/www`;
- service reload;
- Edge1 deployment or cutover.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, Fail2ban, routing, proxying, IDS, reputation list, authentication boundary, certificate, listener, public access, published file, deletion, or production traffic is changed or authorized by this design.
