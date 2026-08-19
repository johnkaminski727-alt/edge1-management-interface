# Edge1 Front Door — Agent State

Last reconciled: 2026-08-19  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Status: **LIVE / ACCEPTED / REVERIFIED**

## Mission

Provide a minimal public/default Edge1 web front door without exposing internal services. Canonical public destination is exactly `https://ww.cx/time/`.

## Repository implementation

The front-door implementation was prepared and validated through PR #447. The live implementation commit is:

```text
74e7b1a6d19edebaf42c69df8d57838eb52eee78
```

The production Edge1 checkout was fast-forwarded from `e74016d89cafd3d33d0ef14a388669f16cda2877` to that commit before the live cutover.

## Accepted live behavior

The approved cutover completed on 2026-08-19 with `EDGE1_FRONT_DOOR_LOCAL_ACCEPTANCE=PASS`.

Accepted response matrix:

- raw/default IPv4 HTTP `/`: `302 -> https://ww.cx/time/`;
- unmatched Host HTTP `/`: `302 -> https://ww.cx/time/`;
- `edge1.ww.cx` HTTP `/`: existing `301 -> https://edge1.ww.cx/` preserved;
- `edge1.ww.cx` HTTPS `/`: `302 -> https://ww.cx/time/`;
- `edge1.ww.cx` HTTPS `/index.html`: `302 -> https://ww.cx/time/`;
- `/edge1-status/`: `200`, preserved;
- `/edge1-ops/`: `404`, preserved;
- `/api/operations/`: `404` for the captured unauthenticated root probe, preserved;
- synthetic ACME HTTP probe: `404`, preserved;
- unknown HTTPS path: `404`, preserved;
- raw HTTPS default-vhost HTTP behavior after TLS: `200`, unchanged;
- `pbx.ww.cx` root: `302 -> https://pbx.ww.cx/admin/`, preserved;
- `sip.ww.cx` root: `200`, preserved;
- authenticated private-source `/admin/`: `302` to FreePBX config, preserved;
- authenticated private-source `/ucp/`: `200`, preserved.

Apache passed `configtest` before and after the controlled reload. Apache and chrony remained active. Existing TCP 80/443 Apache ownership and UDP 123/TCP 4460 chronyd ownership passed post-change verification.

## Independent browser verification

A connected-browser check initially rendered a stale cached Debian default page at the bare Edge1 root. Cache-busted navigations then independently confirmed the active routing:

- `https://edge1.ww.cx/?wwcx_frontdoor=20260819T0529Z` landed on `https://ww.cx/time/?wwcx_frontdoor=20260819T0529Z`;
- `https://edge1.ww.cx/index.html?wwcx_frontdoor=20260819T0529Z` landed on the same WW.CX Time page;
- `http://89.147.109.253/?wwcx_frontdoor=20260819T0529Z` landed on the same WW.CX Time page;
- `/edge1-status/` still rendered the WW.CX Edge1 Operations Center;
- a synthetic unknown non-root HTTPS path still rendered `404 Not Found`.

The connected browser is on the approved private management environment, so it is not independent WAN evidence for `/admin/` or `/ucp/` denial. This cutover did not broaden that access policy and introduced no new proxy or listener.

## Post-acceptance re-verification

A fresh read-only operator inspection was completed on Edge1 at `2026-08-19T19:39:47Z` and repeated at `2026-08-19T19:39:56Z`.

Verified facts:

- host: `edge1.ww.cx`;
- operator: `wwadmin`;
- checkout branch: `main`;
- local checkout HEAD at inspection: `94670022e9318c3c0364bd1a9fcb5f326e2124bf`;
- remote `main` reported by `git ls-remote`: `1857e0afaa76a2e1e4f590cab2e2c1d30ce70db9`;
- direct repository comparison confirmed remote `main` is a clean 15-commit fast-forward from the Edge1 checkout, with no divergence;
- neither front-door policy is changed by those 15 commits;
- repository and live SHA-256 values matched for both front-door policy files;
- Apache `configtest`: `Syntax OK`;
- Apache active;
- chrony active;
- HTTP default vhost remains `default.invalid` from `000-default.conf`;
- HTTPS default vhost remains `edge1.ww.cx`;
- the default-HTTP front-door include remains attached to `000-default.conf`;
- the named Edge1 control-surfaces include remains attached to `edge1.ww.cx.conf`;
- raw/default HTTP root: `302 -> https://ww.cx/time/`;
- unmatched HTTP root: `302 -> https://ww.cx/time/`;
- named Edge1 HTTP root: `301 -> https://edge1.ww.cx/`;
- named Edge1 HTTPS `/` and `/index.html`: `302 -> https://ww.cx/time/`;
- `/edge1-status/`: `200`;
- `/edge1-ops/`: `404`;
- `/api/operations/`: `404` for the unauthenticated root probe;
- unknown HTTPS path: `404`;
- default-host and named-host synthetic ACME probes: `404`, preserved;
- raw HTTPS behavior after TLS: `200`, unchanged;
- Apache still owns TCP 80/443;
- chronyd still owns UDP 123 and TCP 4460.

Disposition: **no Apache change, reload, rollback, or new front-door deployment is justified.** The front door remains live, accepted, and verified. The repository checkout lag belongs to separate Edge1 operator/tunnel maintenance and does not reopen this front-door work.

Detailed re-verification record: `docs/control-surfaces/edge1-front-door-reverification-20260819.md`.

## Rollback evidence

Protected live backup:

```text
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z
```

Rollback script:

```text
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z/rollback.sh
```

The backup contains pre/post Apache vhost and listener evidence plus SHA-256 manifests.

## Safety outcome

No DNS, firewall, certificate, authentication, Asterisk, Kamailio, carrier, NTP/NTS, host-clock, or new-listener change was made. No internal service was proxied or newly exposed.

## Deferred

HTTP 302 remains intentional for the accepted rollout. Promotion to HTTP 308 is a separate future decision and must not be performed automatically.
