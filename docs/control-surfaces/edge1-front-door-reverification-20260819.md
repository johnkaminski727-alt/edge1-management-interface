# Edge1 Public Front Door — Post-Acceptance Re-verification

Date: 2026-08-19  
Status: **VERIFIED / NO ACTION REQUIRED**

## Purpose

Record a fresh read-only verification of the already accepted Edge1 public/default web front door so the operational state remains durable outside the originating chat.

This verification did not authorize or perform an Apache mutation, reload, DNS change, firewall change, certificate change, authentication change, listener change, NTP/NTS change, or other production cutover.

## Operator evidence

The authenticated human operator connected to `edge1.ww.cx` and ran the bounded read-only inspection at:

```text
2026-08-19T19:39:47Z
```

The complete inspection was repeated at:

```text
2026-08-19T19:39:56Z
```

Observed identity:

```text
host=edge1.ww.cx
user=wwadmin
branch=main
```

## Repository state

At inspection time:

```text
local HEAD   = 94670022e9318c3c0364bd1a9fcb5f326e2124bf
remote main  = 1857e0afaa76a2e1e4f590cab2e2c1d30ce70db9
```

A repository comparison performed after the live inspection established that remote `main` is exactly 15 commits ahead of the Edge1 checkout, with the Edge1 local HEAD as the merge base and no divergence.

Those 15 commits do not modify either front-door policy file. They concern separate Edge1 operator/tunnel, Business159 operator, documentation, workflow, and related validation work.

The local `origin/main` display in `git status` was therefore only a stale tracking reference because the inspection intentionally used `git ls-remote` rather than mutating/fetching the local repository.

## Policy integrity

Repository source SHA-256 values on Edge1:

```text
3b653223c5f8f8c67de30081df9619080d0e1285dec83385f17ecaf23c125212  deploy/front-door/wwcx-edge1-default-http-front-door.conf
f0616dd40843c84d9bc341f088fc0f0e7938b77d93fbc08049012414d2b57637  deploy/control-surfaces/wwcx-edge1-control-surfaces.conf
```

Live policy SHA-256 values:

```text
3b653223c5f8f8c67de30081df9619080d0e1285dec83385f17ecaf23c125212  /etc/apache2/wwcx-edge1-default-http-front-door.conf
f0616dd40843c84d9bc341f088fc0f0e7938b77d93fbc08049012414d2b57637  /etc/apache2/wwcx-edge1-control-surfaces.conf
```

The repository source and live policy hashes therefore match exactly.

The default front-door include remains attached to:

```text
/etc/apache2/sites-available/000-default.conf
```

The named Edge1 control-surfaces include remains attached to:

```text
/etc/apache2/sites-available/edge1.ww.cx.conf
```

## Apache / vhost state

`apache2ctl configtest` returned:

```text
Syntax OK
```

Observed vhost ordering remains:

- HTTP default: `default.invalid` from `000-default.conf`;
- HTTPS default: `edge1.ww.cx` from `edge1.ww.cx.conf`;
- existing `interconnect.ww.cx`, `portal.ww.cx`, `vpn.ww.cx`, `pbx.ww.cx`, and `sip.ww.cx` named-host structure remains present.

Service state:

```text
apache=active
chrony=active
```

## Fresh response matrix

| Probe | Result |
| --- | --- |
| raw/default HTTP `/` | `302 -> https://ww.cx/time/` |
| unmatched Host HTTP `/` | `302 -> https://ww.cx/time/` |
| `edge1.ww.cx` HTTP `/` | `301 -> https://edge1.ww.cx/` |
| `edge1.ww.cx` HTTPS `/` | `302 -> https://ww.cx/time/` |
| `edge1.ww.cx` HTTPS `/index.html` | `302 -> https://ww.cx/time/` |
| `/edge1-status/` | `200` |
| `/edge1-ops/` | `404` |
| `/api/operations/` root probe | `404` |
| unknown HTTPS path | `404` |
| default-host synthetic ACME probe | `404` |
| named-host synthetic ACME probe | `404` |
| raw HTTPS behavior after TLS | `200` |

This matrix matches the accepted front-door behavior recorded during the original production cutover.

## Listener ownership

Observed listener ownership remains:

- TCP 80: Apache;
- TCP 443: Apache;
- UDP 123: chronyd;
- TCP 4460: chronyd.

No new listener associated with the front-door design was observed.

## Disposition

The Edge1 public/default front door remains **LIVE / ACCEPTED / VERIFIED**.

No Apache change, reload, rollback, or new production front-door deployment is justified by this verification.

The separate 15-commit repository fast-forward is ordinary Edge1 repository maintenance and does not affect or reopen the front-door implementation.

HTTP 302 remains intentional. Promotion to HTTP 308 remains separately deferred and is not authorized by this verification.

## Related durable records

- `.agent/front-door.md`
- `docs/control-surfaces/edge1-front-door-live-acceptance-20260819.md`
- live rollback evidence: `/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z`
- rollback script: `/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z/rollback.sh`
