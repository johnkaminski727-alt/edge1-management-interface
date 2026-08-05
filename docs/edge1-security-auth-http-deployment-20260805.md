# Edge1 Security authentication HTTP adapter deployment handoff

Date: 2026-08-05

## Delivered boundary

The adapter accepts a one-time Business159 RS256 assertion at the exact exchange route, creates an Edge1-owned opaque session, stores only session and CSRF hashes, and exposes exact session/status/logout/configuration-validation routes. It binds only to loopback when run directly. All authenticated POST requests require the exact Edge1 origin and server-verified CSRF state.

The adapter calls only `security.validate_config` on the existing loopback Operations API. It creates the HMAC signature on Edge1, sends no parameters, returns no raw stdout or stderr to the browser, and records the Operations API event ID in the authentication audit. Reload, log rotation, restart, arbitrary actions, arbitrary paths, and mutation scopes remain unavailable.

## Repository components

- `server/edge1_security_auth_http.py` — strict loopback HTTP adapter and optional server entrypoint.
- `server/edge1_operations_client.py` — exact HMAC client for the single read-only action.
- `server/edge1_security_auth_store.py` — adds hashed CSRF state, persistent rate limits, and duplicate-action guards.
- `config/security/edge1-security-auth-http.json` — disabled repository policy.
- `tests/test_edge1_security_auth_http.py` — status, origin, cookie, CSRF, rate, duplicate, timeout, logout, and event-correlation tests.
- `deploy/edge1-security-auth/preflight.sh` — read-only live inventory.
- `deploy/edge1-security-auth/apache-route.conf.example` — staging route example, not installed.

## Required live inventory before activation

Run the preflight through an authenticated Edge1 execution path and capture evidence. Verify:

- host and principal;
- `/opt/edge1-management-interface` branch, commit, and working tree;
- actual Apache service and TLS virtual-host file;
- whether `proxy`, `proxy_http`, and header modules are present;
- the runtime service account and its narrow access to the public JWKS, state directory, audit directory, and existing Operations API secret;
- current listeners on 8097 and proposed 8108;
- current Operations API health and allowlist;
- backup and rollback locations.

Do not guess the systemd user or Apache configuration path.

## Staging sequence

1. Back up the repository, external configs, Apache virtual-host file, and any existing unit file.
2. Install only the Business159 public JWKS at `/etc/wwcx-edge1-ops/business159-jwks.json`; never install the Business159 private key.
3. Copy the gateway and HTTP JSON policies to `/etc/wwcx-edge1-ops/`, set both `enabled` and `deployment_authorized` to `true`, and leave `live_route_authorized` false until the proxy route is approved.
4. Create `/var/lib/wwcx-edge1-ops  and its audit directory with the verified runtime owner and mode `0700`.
5. Start the adapter on `127.0.0.1:8108` under the verified restricted service account.
6. Verify loopback `/healthz`, rejected non-HTTPS proxy context, rejected wrong host/origin, and missing-cookie/CSRF failures.
7. Add only the four exact proxy routes from the example to the verified TLS virtual host. Validate Apache configuration before reload.
8. Perform one Business159 handoff. Verify session cookies, session status, logout, replay rejection, and matching Business159/Edge1 authentication evidence.
9. Run one `security.validate_config` request. Verify the human result, the Operations API `event_id`, and the correlated Edge1 auth audit entry.
10. Keep all mutation actions disabled.

## Rollback

Remove or disable the four proxy routes and validate/reload Apache. Stop and disable only the new adapter service. Set both external auth configurations to disabled. Preserve the SQLite session/replay database and audit JSONL for evidence. The existing Operations API, security sensor, firewall, DNS, WireGuard, routing, and traffic controls do not require rollback because this package does not modify them.

## Current execution status

Repository implementation and tests can be completed without host access. Live preflight, external key provisioning, service installation, Apache validation/reload, and staging acceptance require an authenticated Edge1 execution path and must not be reported as executed until that path is available.
