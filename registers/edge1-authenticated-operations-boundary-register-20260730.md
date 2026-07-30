# Edge1 Authenticated Operations Boundary Register

Date: 2026-07-30  
Classification: internal security architecture and access-control record  
System: `edge1.ww.cx` / WW.CX Operations Center  
Target: `/edge1-ops/`  
State: repository design; disabled and not deployed

## Objective

Define the fail-closed browser identity, server-side session, route, scope, rate-limit, audit, and response-header boundary required before detailed Edge1 pages or feeds can leave the anonymous `/edge1-status/` tree.

## Assets

| Asset | Function | Boundary |
| --- | --- | --- |
| `config/security/edge1-authenticated-operations-policy.json` | Exact disabled browser/session policy | All activation and live-change flags false |
| `schemas/wwcx-edge1-authenticated-operations-policy-v1.schema.json` | Critical policy shape | Repository validation only |
| `server/edge1_ops_access_policy.py` | Pure route, session-claim, scope, rate-limit, and redacted-audit evaluator | No listener, credentials, session issuance, or persistence |
| `deploy/apache/edge1-ops-authenticated.conf.design` | OIDC-oriented Apache review skeleton | Unconditional deny gates; not active |
| `tests/test_edge1_ops_access_policy.py` | Drift, ambiguity, session, status, scope, audit, and static safety tests | Repository only |
| `docs/security/edge1-authenticated-operations-boundary-20260730.md` | Full architecture, inventory, rollout, and safety design | Repository only |

## Committed state

```json
{
  "status": "design_only",
  "enabled": false,
  "deployment_authorized": false,
  "authentication_change_authorized": false,
  "live_route_authorized": false,
  "anonymous_fallback": false
}
```

No identity provider is selected, and no Apache adapter has been verified on Edge1.

## Provider and credential boundary

The design requires OpenID Connect authorization code with PKCE `S256`, state, nonce, issuer and audience validation, MFA, and subject identity from `sub`.

The repository contains no provider endpoint, client identifier, client secret, token, cookie value, user mapping, or claim expression. External future configuration is reserved under `/etc/wwcx-edge1-ops`.

Refresh tokens and raw token storage are forbidden.

## Session boundary

| Control | Required value |
| --- | --- |
| Session type | server-side |
| Browser value | 32-byte opaque identifier |
| Stored identifier | SHA-256 only |
| Idle timeout | 900 seconds |
| Absolute timeout | 28,800 seconds |
| Rotation | authentication and scope change |
| Persistence | disabled |
| Cookie | `__Secure-wwcx_edge1_ops_session`; Path `/edge1-ops/`; no Domain; Secure; HttpOnly; SameSite Strict |

The pure evaluator rejects invalid issuer, audience, MFA, timestamps, hash, expiry, idle age, absolute age, scopes, and identity.

## Route and status boundary

| Result | Status |
| --- | --- |
| Unknown or ambiguous path | `404` |
| Invalid or missing authenticated session | `401` |
| Valid session missing scope | `403` |
| Disallowed resource method | `405` |
| Rate limit exceeded | `429` |
| Authorized read | `200` |

Detailed resources allow only `GET` and `HEAD`. The future local logout route is a separate POST-plus-CSRF authentication operation and is not implemented here.

Path normalization rejects query strings, fragments, percent encoding, backslashes, duplicate separators, dot segments, control characters, oversize paths, and paths outside `/edge1-ops/`.

Prefix matching is segment bounded.

## Scope matrix

General scope:

```text
edge1.status.detail.read
```

Additional history scope:

```text
security.suricata.history.read
```

General scope covers the restricted landing, Security, Network Defense, bitcoin, mining, reports, and data routes. Suricata history routes require both scopes.

## Rate limits

- general reads: 120 per 60 seconds per session;
- history reads: 30 per 60 seconds per session;
- authentication failures: 10 per 600 seconds per source and subject;
- failure status: `429`.

The evaluator exposes the contract only. Storage and counters are deferred until the live adapter/session inventory.

## Audit boundary

The exact audit event contains only:

```text
schema_version
timestamp
request_id
actor_subject
session_identifier_hash
method
path_classification
required_scopes
authorization_decision
status
reason
```

Raw paths, cookies, tokens, query strings, response bodies, arbitrary claims, and detailed source data are excluded.

Future append-only storage is reserved under `/var/lib/wwcx-edge1-ops/audit` with directory mode `0700` and file mode `0600`.

## Apache design state

The `.design` file:

- is explicitly marked do not install;
- contains no provider or credential directives;
- disables indexes and `.htaccess` overrides;
- declares OIDC authentication and read-only methods;
- sets strict no-store and browser-security headers;
- removes CORS;
- contains no proxy rule;
- retains unconditional `Require all denied` gates for every represented restricted route.

It cannot authorize access in its committed form.

## Validation scope

Repository tests are intended to prove:

- committed policy remains disabled and exact;
- unexpected fields and weakened provider, cookie, status, CORS, audit, route, or scope settings fail validation;
- partial or unverified activation is rejected;
- unknown and ambiguous paths return `404` before authentication;
- invalid sessions return `401`;
- missing scopes return `403`;
- unsupported methods return `405`;
- general and history scopes are separated;
- rate-limit contracts are bounded;
- audit fields are exact and redacted;
- the evaluator has no HTTP server, socket, subprocess, token, cookie, database, Apache, or systemd operation;
- the Apache design remains denied and credential-free;
- no installer exists.

Exact-head workflow results and merge evidence remain pending.

## Live prerequisites

Before any provider choice or implementation, fresh authenticated Edge1 inventory must verify Apache modules and includes, route and header matrices, TLS identity, current detailed assets, filesystem ownership/modes/hashes, loopback services, provider and MFA requirements, session/rate-limit storage, audit capacity, backup, and rollback.

No live inventory was executed in this repository-authoring session because no authenticated Edge1 execution path is available.

## Explicit non-authorization

This phase does not authorize or perform provider registration, client-secret creation, session issuance, user/group changes, Apache module/configuration installation, alias/header/authentication changes, service or listener creation, `/var/www` changes, public or restricted route activation, public cutover, detailed-artifact removal, DNS, certificate, firewall, traffic changes, or data deletion.
