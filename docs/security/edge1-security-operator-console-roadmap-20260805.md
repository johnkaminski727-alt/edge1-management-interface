# Edge1 Security Service Console roadmap

Date: 2026-08-05  
Target route: `/edge1-ops/security/`  
Current state: repository prototype and authentication core; not deployed

## Objective

Provide a human operator with a normal browser interface for the managed Edge1 security sensor. The browser must not construct Operations API signatures, receive privileged secrets, or submit arbitrary commands, paths, service names, URLs, or targets.

The console should answer four questions clearly:

1. Is the managed sensor running and receiving traffic?
2. What security events need attention?
3. What safe maintenance actions are available?
4. What happened after an action, and where is the evidence?

## Existing foundations

- managed Suricata and packet-capture services;
- human-readable security telemetry;
- the live read-only Security Operations page;
- a loopback-only, allowlisted Edge1 Operations API;
- HMAC machine-client authentication, replay protection, bounded execution, and SQLite audit;
- the locked Security Service Console prototype;
- the Business159 WW.CX user and role directory;
- the disabled Business159 assertion and Edge1 session gateway core.

The browser must never call the loopback Operations API directly and must never receive the Operations API HMAC secret. The server-side browser gateway will translate an authenticated and authorized browser request into an exact allowlisted operation.

## Phase 1 — Human interface foundation

Implemented:

- `src/web/edge1-ops/security/index.html`;
- `config/security/edge1-security-operator-console.json`;
- `tests/validate_security_operator_console.py`.

The prototype remains locked. No live route, authentication adapter, service, API, network, firewall, DNS, sensor, or traffic-control change was made.

## Phase 2 — Business159 identity assertion and Edge1 session core

Implemented in the repository and disabled:

- `server/edge1_security_auth_gateway.py`;
- `config/security/edge1-security-auth-gateway.json`;
- `tests/test_edge1_security_auth_gateway.py`;
- authentication architecture and deployment handoff documentation.

Architecture:

1. The operator signs in through the established Business159 WW.CX login.
2. Business159 issues a short-lived, audience-bound, one-time RS256 assertion.
3. Edge1 validates the pinned issuer, audience, signature, time bounds, active state, exact claim set, nonce, replay status, and scopes.
4. Edge1 creates its own opaque server-side session and stores only its SHA-256 hash.
5. Edge1 evaluates exact action scopes independently of the Business159 role name.

Business159 remains authoritative. Edge1 does not access or synchronize its SQLite database, copy password hashes, or accept its PHP session cookie.

Initial permissions:

- `edge1.security.read`;
- `edge1.security.validate`.

Mutation permissions remain registered but locked:

- `edge1.security.rules.reload`;
- `edge1.security.logs.rotate`;
- `edge1.security.restart`.

## Phase 3 — Denied-by-default HTTP adapter

Not implemented by the authentication-core change.

The adapter must:

- expose only exact assertion-exchange, logout, console-read, and validation routes;
- use `Secure`, `HttpOnly`, and `SameSite=Strict` cookies;
- require CSRF protection for state-changing browser requests;
- enforce request-size limits, rate limits, and duplicate-click suppression;
- accept no command text, service name, path, URL, target, or arbitrary operation parameter;
- load only public Business159 verification keys;
- create the machine-client Operations API signature only on the server;
- preserve both the authentication event ID and Operations API event ID;
- normalize and redact technical output;
- fail closed when authentication, session, authorization, CSRF, audit, rate limiting, or API health is unavailable;
- remain unavailable on the production route until separately approved after a fresh live inventory.

## Phase 4 — First read-only action

Action: `security.validate_config`  
Permission: `edge1.security.validate`  
Risk: read-only

Acceptance:

- plain-language confirmation;
- visible progress;
- pass or needs-attention result;
- no restart or runtime mutation;
- evidence identifier and timestamp;
- authenticated-operator audit correlated with the Operations API event ID;
- duplicate-click suppression;
- tested 401, 403, 404, 405, 409, 429, and timeout behavior.

## Phase 5 — Controlled mutations

Each mutation requires a separate implementation review and explicit authorization.

### Load updated detection rules

Action: `security.rules.reload`  
Permission: `edge1.security.rules.reload`

Requires typed confirmation, managed-service preflight, the reviewed reload contract, post-action health and EVE-freshness verification, evidence retention, cooldown, and recovery guidance.

### Rotate security logs

Action: `security.logs.rotate`  
Permission: `edge1.security.logs.rotate`

Requires typed confirmation, managed-path validation, preservation checks, a writable-current-log check, evidence retention, cooldown, and recovery guidance.

### Restart the managed sensor

Permission: `edge1.security.restart`

Requires a new allowlisted backend operation, recent authentication or step-up verification, process-identity checks, capture continuity, service health, fresh nonzero packet acceptance, and rollback evidence.

## Interface requirements

Each action must explain:

- what it does;
- why an operator might use it;
- what it changes and does not change;
- expected duration;
- confirmation requirement;
- progress and result;
- evidence identifier;
- recovery guidance.

Buttons must not silently repeat a request. The browser must disable an in-flight action until completion or timeout.

## Current safety boundary

The repository implementation does not:

- deploy or activate `/edge1-ops/security/`;
- implement the Business159 assertion issuer;
- accept Business159 cookies or password material;
- create a public listener;
- alter Apache or another web-server route;
- enable an Operations API action;
- enable a mutation scope;
- restart, reload, or reconfigure a service;
- change rules, logs, retention, firewall, DNS, WireGuard, routes, NAT, packet capture, or traffic controls.

## Recommended next implementation

Implement the denied-by-default HTTP adapter around the authentication core and the exact `security.validate_config` server-side action bridge. Keep the production route disabled until a fresh Edge1 inventory, complete staging acceptance, and separate activation approval.
