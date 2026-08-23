# Edge1 VPN enrollment portal UI overlay

The live Edge1 VPN enrollment portal is currently installed under `/opt/edge1-vpn-enroll` and is not itself a Git worktree. Its administrative UI was refreshed on 2026-08-23 to match the WW.CX Admin v2 shell, and its separate browser Basic Auth entry point was retired in favor of the authoritative WW.CX administrator identity handoff.

The authoritative visual and account baseline is the WW.CX Admin v2 shell on `ww-cx-website`. The live portal adaptation is documented in `docs/vpn-enrollment-admin-v2-ui.md`.

When the standalone enrollment package is next repackaged, preserve the following requirements in `edge1_vpn_enroll/app.py`:

- Admin v2 navy/cream shell and sticky top bar;
- Christmas Island Worldwide badge;
- grouped sidebar navigation with Network open;
- hidden sidebar scrollbar;
- account-settings link back to `https://ww.cx/admin/account.php`;
- responsive mobile menu and scrim;
- Admin v2 cards, form controls, tables, status pills, and public enrollment card;
- administrator routes must require an active Edge1 session created from the short-lived, one-time Business159/WW.CX identity assertion;
- administrator POST actions must verify the Edge1 CSRF token;
- the legacy `/admin/vpn/...` browser entry point must redirect into the WW.CX identity handoff rather than issue a separate Basic Auth challenge;
- no change to invite, enrollment, peer, revocation, registration, or enforcement logic except the authentication boundary described above.

Current authenticated public surface:

- `https://ww.cx/admin/edge1-vpn-login.php` — WW.CX administrator handoff;
- `https://vpn.ww.cx/edge1-ops/session/exchange` — one-time assertion exchange;
- `https://vpn.ww.cx/edge1-ops/vpn/` — authenticated VPN & Devices administration;
- `https://vpn.ww.cx/edge1-ops/vpn/invites` — authenticated invite management;
- `https://vpn.ww.cx/edge1-ops/vpn/devices` — authenticated device management.

Do not replace the live runtime from this directory. Treat this as deployment guidance until the standalone portal package itself is brought under repository source control.
