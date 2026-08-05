# Edge1 Security Service Console authentication gateway

Date: 2026-08-05  
Tracking: #303  
Status: implemented in repository; disabled; not deployed

## Decision

Business159 remains the authoritative WW.CX user and role directory. Edge1 does not read, copy, synchronize, mount, or remotely query the Business159 SQLite database. It does not receive password hashes and does not accept the Business159 PHP session cookie.

The cross-host boundary is:

1. The operator authenticates on Business159 through the existing WW.CX login.
2. Business159 creates a short-lived, audience-bound, one-time RS256 identity assertion.
3. Edge1 validates the assertion with a pinned public JWK set.
4. Edge1 consumes the assertion nonce atomically and creates an Edge1-owned opaque session.
5. Edge1 stores only a SHA-256 hash of the session identifier.
6. Exact Edge1 action scopes are evaluated independently of the Business159 role name.

The Business159 role is retained as source context, but it does not imply an Edge1 permission.

## Implemented repository boundary

`server/edge1_security_auth_gateway.py` provides:

- strict compact JWS parsing;
- duplicate JSON-key rejection;
- exact `RS256` algorithm enforcement;
- JWK `kid`, key type, use, algorithm, key operation, modulus-size, and exponent validation;
- exact issuer and audience checks;
- exact minimal claim-set validation;
- active-user enforcement;
- bounded `iat`, `nbf`, and `exp` checks;
- maximum assertion lifetime enforcement;
- atomic one-time replay consumption in SQLite;
- Edge1-owned opaque session generation;
- SHA-256-only session identifier storage;
- absolute and idle session expiry;
- logout revocation;
- exact action allowlisting;
- exact permission enforcement;
- independent mutation-scope lockout;
- append-only audit support without raw assertions, cookies, passwords, signatures, or session tokens;
- correlation between the authentication event and the Edge1 Operations API event identifier;
- disabled-by-default activation gating.

The module does not:

- implement the Business159 assertion issuer;
- open a network listener;
- add or activate an Apache route;
- accept browser calls to the loopback Operations API;
- obtain or expose the Operations API HMAC secret;
- execute an Edge1 action;
- enable reload, rotation, restart, or another mutation;
- alter firewall, routing, WireGuard, DNS, NAT, sensor, or traffic settings.

## Assertion contract

Header:

```json
{
  "alg": "RS256",
  "kid": "business159-key-id",
  "typ": "JWT"
}
```

Claims are intentionally minimal and exact:

```json
{
  "iss": "https://business159.ww.cx/wwcx-identity",
  "aud": "urn:wwcx:edge1:security-console",
  "sub": "stable-business159-user-id",
  "display_name": "Operator display name",
  "active": true,
  "role": "source-role-name",
  "scope": [
    "edge1.security.read",
    "edge1.security.validate"
  ],
  "iat": 0,
  "nbf": 0,
  "exp": 0,
  "jti": "unique-assertion-id",
  "nonce": "unique-one-time-nonce"
}
```

Rules:

- `iss` and `aud` must exactly match Edge1 configuration.
- `active` must be `true`.
- `jti` and `nonce` must be distinct, bounded identifiers.
- Assertion lifetime is at most 120 seconds.
- Clock skew is at most 10 seconds in the repository contract.
- The entire assertion is denied when any unknown or mutation scope is present.
- The assertion and nonce are never stored raw.
- A replayed assertion is denied even when its signature remains valid.

## Initial permission model

Enabled by the authentication core:

- `edge1.security.read`
- `edge1.security.validate`

Registered but locked:

- `edge1.security.rules.reload`
- `edge1.security.logs.rotate`
- `edge1.security.restart`

Action mapping:

- `security.console.read` requires `edge1.security.read`.
- `security.validate_config` requires `edge1.security.validate`.
- Unknown actions fail closed.
- Mutation actions fail closed regardless of source role or assertion content.

## Session and revocation model

The Edge1 session is separate from the Business159 session. Repository defaults use a five-minute absolute lifetime and a three-minute idle lifetime. The browser-facing adapter must set a `Secure`, `HttpOnly`, `SameSite=Strict` cookie and must implement CSRF protection before any route activation.

Business159 logout, deactivation, or role change does not cause Edge1 to access Business159 state. The bounded Edge1 session expires independently, and a new session cannot be created unless Business159 issues a new valid assertion. A future immediate-revocation channel would require a separate reviewed design and is not introduced here.

## Audit correlation

A successful assertion exchange creates an Edge1 authentication event identifier. The server-side action adapter must retain that identifier and call `correlate_operations_event` after the loopback Operations API returns its event identifier.

The resulting audit record contains:

- request identifier;
- actor subject;
- hashed Edge1 session identifier;
- authentication event identifier;
- exact action identifier;
- Edge1 Operations API event identifier;
- allow or deny decision and bounded reason.

It does not contain the assertion, signature, cookie, password material, raw session identifier, HMAC secret, or privileged command output.

## Validation

The focused unit suite covers:

- valid assertion exchange;
- invalid signature;
- wrong audience;
- expired assertion;
- inactive identity;
- assertion replay;
- unknown scope;
- mutation scope;
- missing validate permission;
- unknown action;
- locked mutation action;
- idle expiry;
- absolute expiry;
- logout;
- disabled gateway;
- audit outage;
- hashed session storage;
- Operations API event correlation;
- disabled repository configuration and trust-boundary assertions.
