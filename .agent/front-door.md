# Edge1 Front Door — Agent State

Last reconciled: 2026-08-19  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Branch prepared: `agent/edge1-front-door-20260819`

## Mission

Build the minimal public/default Edge1 web front door without exposing internal services. Canonical public destination is exactly `https://ww.cx/time/`.

## Verified live baseline

Authenticated inspection at 2026-08-19T05:14:12Z established:

- host `edge1.ww.cx`, operator `wwadmin`;
- `/opt/edge1-management-interface` clean `main` at `e74016d89cafd3d33d0ef14a388669f16cda2877`;
- local and remote `origin/main` matched that SHA;
- Apache active and `Syntax OK`;
- HTTP default vhost: `default.invalid` / `000-default.conf`;
- HTTPS default vhost: `edge1.ww.cx` / `edge1.ww.cx.conf`;
- current control-surfaces include active in the Edge1 HTTPS vhost;
- raw/unmatched HTTP root returned 200;
- named Edge1 HTTP root returned 301 to HTTPS;
- named Edge1 HTTPS root and `/index.html` returned 302 to `https://creekco.ca/time/`;
- `/edge1-status/` returned 200;
- `/edge1-ops/`, `/api/operations/`, synthetic ACME probe and unknown path returned 404 in the captured local matrix;
- authenticated private-source `/admin/` returned 302 and `/ucp/` 200;
- UDP/123 and TCP/4460 remained owned by chronyd; Apache remained on TCP/80 and TCP/443.

## Decision

Use two narrow root-only policies:

1. update the existing named `edge1.ww.cx` Control Surfaces root redirect to `https://ww.cx/time/`;
2. add a separate root-only include to the `default.invalid` HTTP vhost for raw/unmatched HTTP `/` and `/index.html`.

Do not redirect arbitrary paths. Do not add a proxy. Do not alter raw-IP TLS behavior.

Use HTTP 302 for deployment/acceptance. A later 308 promotion is separate work.

## Safety boundary

Repository work, tests, branch, PR and CI are authorized. The production Apache/public-route mutation is not. Stop immediately before live application and request explicit approval with exact files, route matrix, configtest, rollback and validation plan.

## Remaining sequence

1. publish and validate focused repository branch/PR;
2. merge only when exact-head CI is green;
3. verify production preflight against expected current hashes/state;
4. request explicit live-cutover approval;
5. after approval, backup -> apply smallest change -> configtest -> reload -> full route/listener/NTP/NTS/ACME verification -> preserve rollback evidence;
6. record acceptance and closeout in a follow-up repository change.
