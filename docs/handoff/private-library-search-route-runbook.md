# Private Library Search VPN Route Runbook

Date: 2026-07-18
Classification: internal
Scope: approval-gated VPN-only route with operator authentication

## Status: PREPARED, NOT INSTALLED

Nothing in this track is active until an operator runs the installer on
Edge1 with the explicit approval flag. Preparing these assets does not
expose anything.

This track addresses open handoff items 2 (approved private/VPN route for
browser access) and 3 (operator authentication at the route boundary).

## Approval Boundary

Per the combined project register, route exposure beyond localhost requires
explicit approval. The installer enforces that in four ways: it requires the
`--approve-route-exposure` flag, requires a typed confirmation phrase (or a
deliberate `EDGE1_ROUTE_APPROVAL=I_APPROVE` for non-interactive use), accepts
only private IPv4 (RFC1918) bind addresses that are actually configured on a
local interface, and refuses to run before operator credentials exist.

IPv6 bind addresses are deliberately rejected: the template and smoke test
assume unbracketed IPv4 listen syntax, and Edge1's WireGuard interface uses
a 10.x address. IPv6 support would be a separate, tested change.

Public exposure is not supported by these assets at all.

## Architecture

```text
VPN peer (browser)
  -> WireGuard tunnel (transport encryption)
    -> nginx on <vpn-ip>:8443  [basic auth, GET/HEAD only]
      -> 127.0.0.1:8091 wrapper [read-only, operations collection only]
        -> Big Bird library engine (live_direct)
```

The wrapper's own localhost-only boundary is unchanged; nginx is the only
component that touches the VPN interface, and authentication happens there.

## Prerequisites

1. The managed search service is installed and passing its smoke test
   (`docs/handoff/private-library-search-service-runbook.md`).
2. nginx is installed and running.
3. WireGuard is up and the chosen bind IP is on a local interface
   (`ip -o addr show`).

## Install

```bash
cd /opt/edge1-management-interface

# 1. Create operator credentials (prompts; 12+ char password)
sudo deploy/create-search-route-htpasswd.sh

# 2. Install the route (replace 10.x.x.x with Edge1's WireGuard IP)
sudo deploy/install-private-library-search-route.sh \
  --approve-route-exposure --bind-ip 10.x.x.x
```

Port defaults to 8443; override with `EDGE1_ROUTE_PORT`. Server name
defaults to `edge1-search.internal`; override with `--server-name`.

## Verify

```bash
deploy/private-library-search-route-smoke-test.sh 10.x.x.x 8443
```

Checks, in order: unauthenticated requests get 401; authenticated search
returns valid JSON and reports its mode (expect `live_direct`); POST is
blocked at the route; wrapper port 8091 is still loopback-only; the route
port is bound to the VPN IP only, never all interfaces.

Also verify from an actual VPN peer (phone or laptop on WireGuard) that the
UI loads and search works, and that the same URL is unreachable with the
tunnel down.

Repo-side asset validation (no root, no nginx needed):

```bash
python3 tests/validate_search_route_assets.py
```

## Operate

- Rotate or add operator credentials: rerun
  `sudo deploy/create-search-route-htpasswd.sh` (replaces that user's entry,
  keeps others).
- Route logs: `/var/log/nginx/edge1-search-access.log` and
  `edge1-search-error.log`.

## Rollback

```bash
sudo rm /etc/nginx/conf.d/edge1-private-library-search.conf
sudo nginx -t && sudo systemctl reload nginx
```

The localhost service and manual launch are unaffected by rollback.

## Out of Scope

- Public exposure in any form.
- TLS termination (WireGuard provides transport encryption; a commented TLS
  block exists in the template if layered TLS is wanted later).
- Session-based login/logout UI. Basic auth at the route boundary satisfies
  handoff item 3; a session UI would be a new project decision.
