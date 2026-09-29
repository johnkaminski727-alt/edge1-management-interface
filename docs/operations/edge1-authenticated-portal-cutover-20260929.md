# Edge1 authenticated portal cutover

Date: 2026-09-29

## Purpose

Move the registry-driven Edge1 Control Center under the authenticated `/edge1-ops/` namespace without widening the Edge1 session cookie beyond its existing `/edge1-ops/` path.

## Browser namespace

The accepted read-only status tree is published as:

`/edge1-ops/status/`

Its physical deployment directory remains:

`/var/www/edge1-status/`

This preserves the existing collector/exporter paths while putting browser access beneath the authenticated cookie namespace.

## Authentication flow

1. Client connects through WireGuard.
2. `https://edge1.ww.cx/` challenges unauthenticated browser navigation through the Business159 handoff.
3. Business159 issues the existing short-lived one-time assertion.
4. Edge1 exchanges it for the existing opaque Edge1 session.
5. Successful exchange returns to `/edge1-ops/status/`.
6. The synchronized Control Center menu, mobile drawer, search palette and ToolBox load from the same navigation registry.

API failures remain HTTP errors; API POST requests are never converted into browser-login redirects.

## Required nginx boundary

The private nginx listener remains bound only to `10.77.0.1:443`.

The status tree should be exposed with an nginx `auth_request` subrequest to the existing `/edge1-ops/session` endpoint. The browser already sends the session cookie for this path because the cookie scope is `/edge1-ops/`.

No public 443 listener is authorized.

## Shared shell

The authenticated Control Center and read-only specialist pages consume:

- `/edge1-ops/status/operator-shell/shell.css`
- `/edge1-ops/status/operator-shell/shell.js`
- `/edge1-ops/status/operator-shell/navigation.json`

The console CSP allows only same-origin shared assets plus the existing nonce-bound inline console code. It does not add `unsafe-inline` or external script origins.

## Safety

Navigation remains descriptive. A menu entry does not grant a scope, enable a mutation, or publish an unaccepted module.

AVA, Contacts & Relationships, Firewall, WireGuard/VPN, DNS, Changes & Apply, and Audit & History remain visible according to their registry state and are non-clickable until their browser routes are separately accepted.

## Rollback

Portal route publication must be backup-first. Rollback restores the previous nginx site, previous published status assets and previous runtime auth configuration without modifying the working tree containing concurrent Contacts development.
