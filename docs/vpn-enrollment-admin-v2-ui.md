# VPN Enrollment Admin v2 UI

Status: deployed on Edge1 on 2026-08-23.

## Purpose

Bring the standalone `vpn.ww.cx` WireGuard enrollment portal into the same visual and account system as the WW.CX Admin v2 shell.

The live portal remains a separate Edge1 service. Invite creation, invite redemption, WireGuard peer creation, device revocation, registration synchronization, and VPN enforcement remain unchanged. The administrator authentication boundary is now unified with WW.CX: the old standalone browser Basic Auth prompt is retired.

## Visual baseline

The portal follows the Admin v2 design introduced on the WW.CX website:

- navy/deep-navy application sidebar;
- cream application background;
- white cards with warm neutral borders and soft navy shadow;
- sticky white top bar;
- collapsible grouped navigation with Network open and VPN & Devices active;
- Christmas Island Worldwide badge;
- responsive mobile navigation with overlay scrim;
- hidden sidebar scrollbar;
- account-settings links back to the authoritative WW.CX account page;
- responsive card, form, table, and enrollment layouts.

## Authentication boundary

The VPN administrator surface uses the existing Business159 -> Edge1 identity bridge.

1. The administrator signs in to WW.CX.
2. `/admin/edge1-vpn-login.php` verifies the local WW.CX administrator role.
3. Business159 issues the existing short-lived, audience-bound, one-time RS256 assertion. Password material, the Business159 SQLite database, and the WW.CX session cookie are not sent to Edge1.
4. `vpn.ww.cx/edge1-ops/session/exchange` proxies the assertion to the loopback Edge1 security-auth adapter.
5. Edge1 validates the assertion and creates its own opaque server-side session plus CSRF state.
6. The VPN portal validates that Edge1 session for every administrator request and requires the Edge1 CSRF token for administrator mutations.
7. Replaying an assertion is denied.

The Edge1 HTTP server now speaks HTTP/1.1 and supplies final `Content-Length` headers so Apache `Expect: 100-continue` proxy requests cannot deadlock while submitting the assertion.

## Live implementation

Runtime service: `edge1-vpn-enroll.service`

Runtime application: `/opt/edge1-vpn-enroll/edge1_vpn_enroll/app.py`

Authenticated routes:

- `https://ww.cx/admin/edge1-vpn-login.php` — WW.CX administrator handoff;
- `https://vpn.ww.cx/edge1-ops/session/exchange` — Edge1 assertion exchange;
- `https://vpn.ww.cx/edge1-ops/vpn/` — VPN & Devices administration;
- `https://vpn.ww.cx/edge1-ops/vpn/invites` — invite management;
- `https://vpn.ww.cx/edge1-ops/vpn/devices` — device management.

Legacy `https://vpn.ww.cx/admin/vpn/...` routes redirect to the WW.CX administrator handoff and no longer issue an independent browser login challenge.

Public enrollment remains at `https://vpn.ww.cx/enroll/i/<token>`.

## Dashboard improvements

The VPN & Devices dashboard includes summary cards for active enrolled devices, open invites, configured tunnel profiles, and the Edge1 VPN gateway. Invite creation uses the Admin v2 form layout, and invite/device tables use responsive bordered table containers.

## Validation

Completed on Edge1 after deployment:

- Python compilation passed;
- `edge1-security-auth.service`, `edge1-vpn-enroll.service`, and Apache remained active;
- unauthenticated VPN administrator requests redirect to the WW.CX handoff;
- one-time assertion exchange returned `303` and established an Edge1 session;
- authenticated session verification succeeded;
- authenticated VPN administrator page returned `200`;
- assertion replay returned `401`;
- logout returned to WW.CX and the Edge1 session was rejected afterward;
- legacy `/admin/vpn/...` no longer presents Basic Auth;
- mutation scopes remain disabled in the Edge1 security-auth boundary.

## Safety boundary

This work does not change WireGuard routing, DNS, firewall policy, peer address allocation, registration policy, or VPN enforcement. WW.CX remains authoritative for the administrator role, and Edge1 continues to own and validate its short-lived local session after the handoff.
