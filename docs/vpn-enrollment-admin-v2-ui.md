# VPN Enrollment Admin v2 UI

Status: deployed on Edge1 on 2026-08-23.

## Purpose

Bring the standalone `vpn.ww.cx` WireGuard enrollment portal into the same visual system as the WW.CX Admin v2 shell that is used across the Store and administration pages.

The live portal remains a separate Edge1 service. This change is presentation-only: invite creation, invite redemption, WireGuard peer creation, device revocation, registration synchronization, authentication boundaries, and VPN enforcement state are unchanged.

## Visual baseline

The portal follows the Admin v2 design introduced on the WW.CX website and rolled across Store pages on 2026-08-23:

- navy/deep-navy application sidebar (`#123f60` / `#0b2f49`);
- cream application background (`#f7f4ee`);
- white cards with warm neutral borders and soft navy shadow;
- sticky white top bar;
- collapsible grouped navigation with Network open and VPN & Devices active;
- Christmas Island Worldwide badge in the upper-left brand area;
- responsive mobile navigation with an overlay scrim;
- hidden sidebar scrollbar;
- account-settings links back to the authoritative WW.CX admin account page;
- responsive card, form, table, and enrollment layouts.

## Live implementation

Runtime service: `edge1-vpn-enroll.service`

Runtime application: `/opt/edge1-vpn-enroll/edge1_vpn_enroll/app.py`

Public routes:

- `https://vpn.ww.cx/admin/vpn/` — protected VPN & Devices administration shell;
- `https://vpn.ww.cx/admin/vpn/invites` — invite management;
- `https://vpn.ww.cx/admin/vpn/devices` — device management;
- `https://vpn.ww.cx/enroll/i/<token>` — branded public invite redemption.

The public enrollment screen uses the same colors, typography, badge, card treatment, and responsive conventions without exposing the administrative sidebar.

## Dashboard improvements

The VPN & Devices dashboard now includes summary cards for:

- active enrolled devices;
- open invites;
- configured tunnel profiles;
- the Edge1 VPN gateway.

Invite creation uses the Admin v2 form layout, and invite/device tables use responsive bordered table containers. Existing revoke actions are unchanged.

## Validation

Completed on Edge1 after deployment:

- Python compilation passed;
- existing VPN enrollment unit test passed;
- Admin v2 shell render smoke passed;
- Christmas Island brand asset, Network navigation, account link, and responsive shell markers are present;
- live `edge1-vpn-enroll.service` restarted and remained active;
- protected public admin route still returns `401` without authentication;
- slashless admin route still redirects to `/admin/vpn/`;
- create-invite HTTP form returned `200`;
- the test invite was revoked successfully;
- Edge1 operations health remained `ok`;
- VPN registration stayed enabled while VPN enforcement stayed disabled.

## Safety boundary

This UI refresh does not change WireGuard configuration, peer policy, routing, DNS, firewall rules, authentication policy, registration policy, or enforcement. It does not make the VPN admin page public.
