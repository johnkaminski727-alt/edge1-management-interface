# Edge1 Security authenticated console route cutover

Date: 2026-08-06

## Verified live facts

The live inventory established that the Business159 administration endpoint is served from `https://ww.cx/admin/edge1-security-login.php`. The retired design hostname `business159.ww.cx` has no DNS resolution or TLS identity and must not be accepted as the browser `Origin` value.

Edge1 currently runs the authentication adapter on `127.0.0.1:8108`. The public JWKS is installed, the private signing key remains only on Business159, the Operations API remains on `127.0.0.1:8097`, and all mutation actions remain disabled. Before route activation, Apache has no `/edge1-ops/` authentication routes and the repository console file is not exposed through an alias.

## Repository corrections

This change:

- changes the exact accepted assertion-submission browser origin to `https://ww.cx`;
- keeps the assertion issuer identifier unchanged;
- adds `/edge1-ops/security/` to the adapter route contract;
- serves the console only after validating an Edge1 session with `edge1.security.read`;
- injects a per-response CSP nonce into the single inline style and script blocks;
- enables only the read-only `security.validate_config` browser action;
- enforces `live_route_authorized` for every route except loopback health;
- retains exact host, forwarded-HTTPS, loopback, CSRF, rate-limit, audit, and Operations API boundaries;
- keeps reload, rotation, restart, arbitrary actions, and all mutation scopes unavailable.

## Deployment sequence

1. Merge and deploy the reviewed repository change to Edge1.
2. Update the external HTTP policy to the real browser origin and the console route while keeping `live_route_authorized=false`.
3. Restart only `edge1-security-auth.service` and verify health remains available while every non-health route returns `503`.
4. Set only the external HTTP policy `live_route_authorized=true`.
5. Install the five adapter proxy routes from `deploy/edge1-security-auth/apache-route.conf.example` into the verified Edge1 TLS virtual host.
6. Validate Apache configuration before reload and immediately verify unauthenticated console/session requests return `401`, invalid assertion exchange from `https://ww.cx` reaches assertion validation, and the retired origin is rejected.
7. Enable the Business159 bridge only after the Edge1 public routes pass negative acceptance.
8. Perform one administrator handoff, verify secure cookies, authenticated console rendering, session status, one read-only configuration validation, evidence correlation, logout, and assertion replay denial.

## Rollback

Restore the backed-up Apache virtual host and external HTTP policy, validate and reload Apache, and restart only `edge1-security-auth.service`. Disable the Business159 bridge. Preserve the Edge1 replay/session database, authentication audit, Operations API evidence, and all deployment evidence. Do not modify firewall, DNS, routing, WireGuard, Suricata, packet capture, or unrelated services.
