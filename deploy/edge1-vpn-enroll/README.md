# Edge1 VPN enrollment portal UI overlay

The live Edge1 VPN enrollment portal is currently installed under `/opt/edge1-vpn-enroll` and is not itself a Git worktree. Its administrative UI was refreshed on 2026-08-23 to match the WW.CX Admin v2 shell.

The authoritative visual baseline is the WW.CX Admin v2 shell on `ww-cx-website`. The live portal adaptation is documented in `docs/vpn-enrollment-admin-v2-ui.md`.

When the standalone enrollment package is next repackaged, preserve the following presentation requirements in `edge1_vpn_enroll/app.py`:

- Admin v2 navy/cream shell and sticky top bar;
- Christmas Island Worldwide badge;
- grouped sidebar navigation with Network open;
- hidden sidebar scrollbar;
- account-settings link back to `https://ww.cx/admin/?page=account`;
- responsive mobile menu and scrim;
- Admin v2 cards, form controls, tables, status pills, and public enrollment card;
- no change to the existing invite, enrollment, peer, revocation, registration, or enforcement logic.

Do not replace the live runtime from this directory. Treat this as deployment guidance until the standalone portal package itself is brought under repository source control.
