# Private Library Search VPN Route Register - 2026-07-18

| Item | Status | Evidence |
| --- | --- | --- |
| nginx route template | Prepared | `deploy/nginx/edge1-private-library-search.conf.template` |
| Approval-gated installer | Prepared | `deploy/install-private-library-search-route.sh` |
| Operator credential helper | Prepared | `deploy/create-search-route-htpasswd.sh` |
| Route smoke test | Prepared | `deploy/private-library-search-route-smoke-test.sh` |
| Operator runbook | Prepared | `docs/handoff/private-library-search-route-runbook.md` |
| Repo-side asset validation | Passing | `python3 tests/validate_search_route_assets.py` |
| Route exposure approval | NOT GIVEN | Required before any install |
| Install on Edge1 | Blocked on approval | Requires root + `--approve-route-exposure` |
| VPN-peer browser walkthrough | Pending | Open handoff item 5 |

## Boundary Notes

- Nothing is exposed by merging this track; all assets are inert until the
  operator runs the installer with the approval flag on Edge1.
- The installer refuses: missing approval flag, missing typed confirmation,
  non-private bind addresses, addresses not present on a local interface,
  and missing operator credentials.
- The wrapper's localhost-only boundary is unchanged; authentication happens
  at nginx (open handoff item 3), which proxies GET/HEAD only.

## Operator Next Actions (in order, all on Edge1)

1. Complete the managed-service track first (service register 20260718).
2. Decide whether route exposure is approved. If not, stop; nothing to do.
3. `sudo deploy/create-search-route-htpasswd.sh`
4. `sudo deploy/install-private-library-search-route.sh --approve-route-exposure --bind-ip <wireguard-ip>`
5. `deploy/private-library-search-route-smoke-test.sh <wireguard-ip> 8443`
6. Browser walkthrough from a VPN peer; record results here.
