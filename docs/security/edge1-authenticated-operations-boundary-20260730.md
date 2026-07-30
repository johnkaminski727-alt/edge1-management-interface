# Edge1 Authenticated Operations Browser and Session Boundary

Date: 2026-07-30  
System: `edge1.ww.cx` / WW.CX Operations Center  
Target restricted root: `/edge1-ops/`  
State: repository design and policy evaluation only; disabled and not deployed

## Objective

Define a fail-closed browser authentication, server-side session, route authorization, rate-limit, audit, and response-header boundary for detailed Edge1 operations.

This phase does not select an identity provider, configure credentials, issue a browser session, open a listener, install an Apache file, change authentication, or move any detailed artifact from the existing `/edge1-status/` tree.

The anonymous minimized public summary remains a separate surface at `/edge1-status/`.

## Why browser access is a separate trust boundary

The existing loopback Edge1 Operations API uses signed HMAC requests, timestamp validation, nonces, and machine-client audit records. That pattern is appropriate for approved service clients but is not copied into browser JavaScript. A browser must never receive or retain the API signing secret.

The browser design instead requires an external OpenID Connect provider, authorization-code flow, PKCE `S256`, state and nonce checks, issuer and audience validation, and MFA. Provider configuration and all secret material must remain outside the repository.

No identity provider is selected in this phase. No claim syntax is assumed until the actual provider and Apache adapter are inventoried and tested.

## Repository assets

| Asset | Purpose | Activation state |
| --- | --- | --- |
| `config/security/edge1-authenticated-operations-policy.json` | Exact disabled browser/session/route policy | Disabled |
| `schemas/wwcx-edge1-authenticated-operations-policy-v1.schema.json` | Machine-readable critical policy shape | Repository only |
| `server/edge1_ops_access_policy.py` | Pure policy, path, session-claim, scope, rate-limit, and audit-event evaluator | No listener or persistence |
| `deploy/apache/edge1-ops-authenticated.conf.design` | Explicitly denied Apache/OIDC design skeleton | Design only; not active |
| `tests/test_edge1_ops_access_policy.py` | Policy drift, authorization, privacy, path, session, and Apache boundary tests | Repository validation only |

No installer, systemd service, login service, callback handler, session database, provider configuration, client identifier, client secret, token cache, or active Apache file is included.

## Activation gates

The committed policy remains:

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

Partial activation is forbidden. Any future enabled policy must also prove:

- identity provider selected and verified;
- Apache adapter inventoried and verified;
- server-side session store verified;
- authorized and unauthorized route matrices verified;
- append-only audit verified;
- rate limits verified;
- live change explicitly authorized.

The Apache design contains unconditional `Require all denied` gates. It cannot grant access without a later reviewed change that replaces those gates with verified provider-specific scope expressions.

## Provider boundary

Required protocol design:

- OpenID Connect;
- authorization-code flow;
- PKCE `S256`;
- discovery metadata;
- state and nonce validation;
- trusted issuer allowlist;
- audience validation;
- MFA;
- subject identity from `sub`;
- no refresh tokens;
- no raw token storage.

External paths reserved for a future authorized implementation:

```text
/etc/wwcx-edge1-ops/oidc.json
/etc/wwcx-edge1-ops/client-secret
```

Those paths are policy references only. They are not created or read by the repository evaluator.

The preferred Apache adapter is recorded as `mod_auth_openidc`, but module availability, package version, provider compatibility, session-cache behavior, claim expressions, and failure responses remain unverified until a fresh authenticated host inventory.

## Session boundary

A future browser session must be server-side and use only an opaque browser identifier.

| Property | Required value |
| --- | --- |
| Opaque identifier entropy | 32 bytes |
| Stored identifier | SHA-256 hash only |
| Idle timeout | 900 seconds |
| Absolute timeout | 28,800 seconds |
| Clock skew allowance | 60 seconds |
| Rotation | authentication and scope change |
| Logout | server-side invalidation |
| Persistence | disabled |

Cookie contract:

```text
Name: __Secure-wwcx_edge1_ops_session
Path: /edge1-ops/
Domain: absent
Secure: true
HttpOnly: true
SameSite: Strict
```

The policy evaluator accepts already-authenticated session claims only. It rejects unresolved identity, untrusted issuer, invalid audience, missing MFA, malformed session hash, expired session, idle timeout, absolute timeout, invalid timestamps, duplicate scopes, and oversized scope sets.

It never receives or records a raw cookie or token.

## Request and route boundary

Detailed resources allow only `GET` and `HEAD`.

The local logout endpoint is an authentication-infrastructure exception requiring `POST` and CSRF protection. It is outside the read-resource evaluator and is not implemented in this phase.

Status behavior:

| Condition | Status |
| --- | --- |
| Unknown or ambiguous restricted path | `404` |
| Known route without a valid authenticated session | `401` |
| Valid session missing a required scope | `403` |
| Unsupported method on a known resource | `405` |
| Rate limit exceeded | `429` |

API authentication failures must not redirect. Browser navigation may use an OIDC challenge only after the provider and adapter are configured.

Paths are rejected if they contain query strings, fragments, percent encoding, backslashes, duplicate separators, dot segments, control characters, leave `/edge1-ops/`, or exceed 2,048 UTF-8 bytes.

Prefix rules enforce a segment boundary. For example, the history API route does not authorize a similarly named path such as `historyevil`.

## Scope and route matrix

General scope:

```text
edge1.status.detail.read
```

Additional Suricata-history scope:

```text
security.suricata.history.read
```

| Route | Match | Required scopes | Rate class |
| --- | --- | --- | --- |
| `/edge1-ops/` | exact | general | general |
| `/edge1-ops/security/` | prefix | general | general |
| `/edge1-ops/network-defense/` | prefix | general | general |
| `/edge1-ops/bitcoin/` | prefix | general | general |
| `/edge1-ops/mining/` | prefix | general | general |
| `/edge1-ops/reports/` | prefix | general | general |
| `/edge1-ops/data/` | prefix | general | general |
| `/edge1-ops/security/history/` | prefix | general and history | history |
| `/edge1-ops/api/v1/security/suricata/history` | segment-bounded prefix | general and history | history |

Unknown paths are not absorbed by a broad catch-all rule.

## Rate-limit contract

| Class | Limit | Key |
| --- | --- | --- |
| General restricted reads | 120 requests per 60 seconds | session |
| History reads | 30 requests per 60 seconds | session |
| Authentication failures | 10 attempts per 600 seconds | source and subject |

The pure evaluator returns the applicable contract. It does not implement counters or storage. A future authorized session boundary must provide tested rate-limit state and fail closed when that state is unavailable.

## Audit boundary

Required events:

- login started, succeeded, or failed;
- logout;
- session expiry;
- authorization denial;
- rate limiting;
- restricted read.

Exact audit fields:

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

The evaluator creates a redacted event object only. It records a route classification rather than the raw path. Cookies, tokens, query strings, response bodies, arbitrary claims, and private source contents are excluded.

A future writer must be append-only under `/var/lib/wwcx-edge1-ops/audit`, with directory mode `0700` and file mode `0600`.

## Response boundary

Required restricted-route headers:

```text
Cache-Control: no-store, max-age=0
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'
Referrer-Policy: no-referrer
X-Content-Type-Options: nosniff
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
Access-Control-Allow-Origin: absent
Directory listing: disabled
```

Unknown identity, unavailable policy, unavailable session state, untrusted issuer, invalid audience, missing MFA, and missing scope all fail closed. Public error bodies must not expose provider, token, claim, stack, path, or configuration details.

## Apache design boundary

`deploy/apache/edge1-ops-authenticated.conf.design` is intentionally not an active `.conf` file. It:

- begins with a do-not-install warning;
- contains no issuer, client identifier, client secret, or claim mapping;
- aliases only the proposed `/edge1-ops/` root;
- disables directory listing and `.htaccess` overrides;
- declares OIDC authentication;
- limits resources to `GET` and `HEAD`;
- sets the exact restricted headers;
- removes CORS;
- contains no proxy rule;
- retains unconditional deny gates for the general and history routes.

The file is a review artifact, not deployable configuration.

## Required fresh live inventory

Before selecting a provider or implementing a session service, an authenticated read-only Edge1 pass must capture:

- exact Apache version, loaded modules, virtual hosts, includes, aliases, authentication directives, headers, and configuration-test result;
- availability and version of the preferred OIDC adapter or any approved alternative;
- current `/edge1-status/` and `/edge1-ops/` route matrix, redirects, status codes, headers, and TLS identity;
- current public and restricted filesystem paths, ownership, modes, symlinks, and SHA-256 inventories;
- current loopback listeners and reverse proxies;
- identity-provider issuer, audience, MFA, group/scope mapping, callback, logout, and failure requirements without storing secrets in evidence;
- available server-side session cache and rate-limit storage mechanisms;
- audit storage capacity, rotation, backup, and evidence preservation;
- current detailed pages and feeds to be staged under `/edge1-ops/`;
- rollback assets and exact route restoration procedure.

No current live claim is made because an authenticated Edge1 execution path is unavailable in this repository-authoring session.

## Future implementation sequence

A later repository phase may implement a provider-neutral session-store and audit contract only after the live inventory resolves the adapter and storage design.

A later authorized staging phase must:

1. preserve the existing public routes and files;
2. install the restricted surface under a non-public staging root;
3. configure external provider material without committing credentials;
4. verify 401, 403, 404, 405, and 429 behavior;
5. verify valid general and history access separately;
6. verify cookie flags, session rotation, idle and absolute expiry, logout, CSRF, audit, and rate limits;
7. prove no anonymous fallback and no new public listener;
8. capture protected terminal evidence.

Public cutover and detailed-artifact removal remain separate exact-authorized actions after the restricted surface is accepted.

## Safety boundary

No identity provider was selected. No credential, token, cookie, secret, user, group, Apache include, module, alias, header, route, authentication rule, session store, audit file, listener, DNS, certificate, firewall, traffic control, `/var/www` file, public artifact, or production traffic was created or changed.
