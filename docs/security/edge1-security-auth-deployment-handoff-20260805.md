# Edge1 Security authentication deployment handoff

Date: 2026-08-05  
Tracking: #303  
Branch: `agent/edge1-security-auth-gateway`  
Deployment state: not deployed; no live route or service change authorized by this pull request

## Delivered

- Business159 assertion-validation and Edge1 session core.
- Disabled repository configuration.
- Security Console action-to-scope declarations.
- Unit and policy validation in CI.
- Audit correlation primitive for Edge1 Operations API event IDs.

## Preconditions for a staged deployment

Do not activate the gateway until all of the following are complete:

1. A fresh Edge1 live-boundary inventory confirms the intended existing web server, TLS identity, runtime user, filesystem paths, and loopback Operations API state.
2. Business159 implements the reviewed assertion issuer without exposing its SQLite database, password hashes, or PHP session cookie.
3. A Business159 RS256 public JWK set is transferred to Edge1 through an approved configuration-management path.
4. The issuer and Edge1 audience values are confirmed exactly on both hosts.
5. The HTTP adapter is implemented with `Secure`, `HttpOnly`, and `SameSite=Strict` cookie handling, CSRF protection, request-size limits, rate limits, duplicate-click suppression, and no anonymous fallback.
6. The adapter exposes only exact routes for assertion exchange, logout, console read, and configuration validation.
7. The adapter can reach the loopback Operations API without exposing its HMAC secret or signing fields to browser JavaScript.
8. Staging tests cover 401, 403, 404, 405, 409, 429, timeout, audit outage, key mismatch, replay, session expiry, and Operations API unavailability.
9. Mutation actions remain disabled.
10. A separate explicit approval authorizes the staged route and directly affected service reload.

## Configuration placement

Repository example:

- `config/security/edge1-security-auth-gateway.json`

Proposed Edge1 runtime files after approval:

- `/etc/wwcx-edge1-ops/security-auth-gateway.json`
- `/etc/wwcx-edge1-ops/business159-jwks.json`
- `/var/lib/wwcx-edge1-ops/security-auth.sqlite3`
- `/var/lib/wwcx-edge1-ops/audit/security-auth.jsonl`

Only the Business159 public verification keys belong on Edge1. Do not place a Business159 private signing key, user database, password hash, PHP session file, or Operations API HMAC secret in the repository or browser-visible configuration.

Recommended ownership and modes must be confirmed against the actual service account during the fresh inventory. The intended baseline is a service-owned configuration directory, `0700` state and audit directories, and `0600` state and audit files.

## Staged acceptance sequence

1. Back up the directly affected Edge1 operator-gateway files and configuration.
2. Install the reviewed module and disabled configuration without creating a public route.
3. Validate configuration parsing and local state-store creation under the intended service account.
4. Load a non-production Business159 public test key.
5. Exchange a test assertion through a loopback-only or otherwise denied-by-default staging adapter.
6. Verify the assertion can be used once and cannot be replayed.
7. Verify Edge1 stores only session and nonce hashes.
8. Verify logout, idle expiry, absolute expiry, inactive identity, wrong audience, invalid signature, unknown scope, and audit outage all deny access.
9. Verify `security.console.read` and `security.validate_config` separately.
10. Invoke only the read-only `security.validate_config` action and confirm the authentication event ID is correlated with the Operations API event ID.
11. Confirm no browser response or log contains assertions, session tokens, cookies, HMAC material, signing headers, command lines, or unbounded privileged output.
12. Confirm reload, rotation, restart, and all unknown actions remain denied.
13. Capture the staged acceptance evidence and obtain separate route-activation approval.

## Rollback

The authentication core introduces no packet-path or production route change by itself. For a future staged activation, rollback is:

1. Disable the staged authentication route.
2. Stop or reload only the directly affected operator-gateway web adapter after approval.
3. Restore the backed-up adapter and configuration files.
4. Preserve the audit file and state database as evidence; do not delete them during rollback.
5. Confirm `/edge1-ops/security/` is denied and `/edge1-status/security/` remains unchanged.
6. Confirm the loopback Operations API and security sensor services remain in their pre-change state.

Rollback must not modify firewall, routing, WireGuard, DNS, NAT, Suricata configuration, packet capture, or unrelated services.

## Remaining implementation work

This pull request deliberately does not add a live HTTP adapter or Business159 issuer. The next focused change should implement the denied-by-default HTTP adapter and its CSRF/rate-limit behavior, using this authentication core. The Business159 assertion issuer should be developed and reviewed in its authoritative repository, not in Edge1.
