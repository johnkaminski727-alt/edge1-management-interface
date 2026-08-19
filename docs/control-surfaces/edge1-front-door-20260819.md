# Edge1 Public Front Door

Date: 2026-08-19  
Status: repository-prepared; production cutover requires explicit approval

## Objective

Canonicalize ordinary raw/default Edge1 HTTP traffic and the exact `edge1.ww.cx` browser root to:

```text
https://ww.cx/time/
```

This is a public front door only. It must not expose or proxy internal Edge1 services.

## Fresh live baseline

Authenticated host inspection on 2026-08-19 verified:

- repository `/opt/edge1-management-interface` on clean `main` at `e74016d89cafd3d33d0ef14a388669f16cda2877`, matching local and remote `origin/main`;
- Apache configuration syntax `Syntax OK` and service active;
- port 80 default vhost is `default.invalid` from `/etc/apache2/sites-enabled/000-default.conf`;
- port 443 default vhost is `edge1.ww.cx` from `/etc/apache2/sites-enabled/edge1.ww.cx.conf`;
- named Edge1 HTTPS vhost already includes `/etc/apache2/wwcx-edge1-control-surfaces.conf`;
- current named Edge1 root and `/index.html` return HTTP 302 to `https://creekco.ca/time/`;
- current raw/default HTTP root returns HTTP 200;
- `/edge1-status/` returns HTTP 200;
- `/edge1-ops/`, `/api/operations/`, the synthetic ACME probe, and an unknown path returned HTTP 404 during the captured local matrix;
- `/admin/` returned HTTP 302 to FreePBX config and `/ucp/` returned HTTP 200 from the authenticated private source path;
- Apache still listens on TCP 80/443; chronyd still owns UDP 123 and TCP 4460.

The earlier connected-browser observation that rendered the Debian default page conflicts with the host-local root response. Fresh host-side Apache/vhost evidence is authoritative for configuration design; independent post-change outside-in validation remains required.

## Design

### Named `edge1.ww.cx` HTTPS root

Keep the existing root-only Control Surfaces rewrite contract but change its target from `https://creekco.ca/time/` to `https://ww.cx/time/`.

The rule continues to match only `/` and `/index.html`, leaving all other parent-vhost aliases, proxies and application routes untouched.

### Raw/default HTTP root

Add a separate repository-managed include for the `default.invalid` `*:80` vhost. It matches only `/` and `/index.html` and redirects them with HTTP 302 to `https://ww.cx/time/`.

It intentionally does not redirect arbitrary non-root paths. In particular it does not proxy, rewrite, or consume `/vpn/`, ACME paths, operational paths or unknown paths.

### Raw HTTPS IP

No TLS workaround is introduced. The HTTPS default vhost remains hostname/certificate based; certificate validation occurs before an HTTP redirect can fix a raw-IP browser warning.

### Redirect status

Use HTTP 302 during rollout and acceptance. Promotion to 308 is a separate later decision after complete live validation.

## Repository assets

- `deploy/control-surfaces/wwcx-edge1-control-surfaces.conf` — exact named Edge1 root redirect plus existing private FreePBX boundary;
- `deploy/front-door/wwcx-edge1-default-http-front-door.conf` — root-only default/raw HTTP policy;
- `deploy/front-door/install-edge1-default-http-front-door.sh` — guarded backup/configtest/reload/rollback installer for the default HTTP vhost;
- `tests/test_edge1_front_door_apache_policy.py` — root/preservation/no-proxy/no-loop/static installer contract tests;
- `tests/test_control_surfaces_apache_policy.py` — updated canonical target assertion;
- `.github/workflows/control-surfaces.yml` — CI coverage for both Apache policy surfaces.

## Proposed production files

Existing:

```text
/etc/apache2/wwcx-edge1-control-surfaces.conf
```

New:

```text
/etc/apache2/wwcx-edge1-default-http-front-door.conf
```

Modified only to attach the new include:

```text
/etc/apache2/sites-available/000-default.conf
```

No DNS, firewall, certificate, listener, NTP/NTS, Asterisk, Kamailio, carrier, clock-sync or authentication change is part of this front-door cutover.

## Preservation matrix

| Request class | Proposed behavior |
| --- | --- |
| raw/default HTTP `/` | 302 -> `https://ww.cx/time/` |
| raw/default HTTP `/index.html` | 302 -> `https://ww.cx/time/` |
| raw/default HTTP non-root paths | unchanged |
| `edge1.ww.cx` HTTP `/` | existing HTTP->HTTPS canonicalization, then HTTPS root rule |
| `edge1.ww.cx` HTTPS `/` | 302 -> `https://ww.cx/time/` |
| `edge1.ww.cx` HTTPS `/index.html` | 302 -> `https://ww.cx/time/` |
| `/edge1-status/` | unchanged |
| `/edge1-ops/` | unchanged |
| `/api/operations/` and other explicit proxy routes | unchanged |
| `/mcp/wwcx-timekeeping...` | unchanged |
| `/api/electrum-watch...` | unchanged |
| `/admin/`, `/ucp/` | existing Control Surfaces access policy unchanged |
| `/.well-known/acme-challenge/...` | unchanged |
| raw HTTPS IP | no certificate workaround; HTTP behavior after TLS remains default-vhost behavior |

## Production gate

Before applying, re-check branch/head/working tree, current hashes, vhost ordering and `apache2ctl configtest`. Back up each exact live file. Apply only the two repository-owned policy changes, run configtest, reload Apache rather than restart, and execute the full response matrix.

If any expected hash, include placement, vhost structure or route behavior has drifted, stop rather than improvising.

Explicit user approval is required immediately before the production Apache/public-routing mutation.
