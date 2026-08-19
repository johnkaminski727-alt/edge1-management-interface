# Edge1 Public Front Door — Live Acceptance

Date: 2026-08-19  
Status: **LIVE / ACCEPTED**

## Scope

This record closes the approved Edge1 public/default web front-door cutover. The canonical public destination is:

```text
https://ww.cx/time/
```

The change is intentionally narrow: raw/default HTTP root traffic and the exact named Edge1 HTTPS root are redirected to WW.CX Time. Existing non-root application, operational, ACME and private-control behavior is preserved.

## Repository provenance

Implementation PR: #447, `Prepare Edge1 public front door`.

Live implementation commit:

```text
74e7b1a6d19edebaf42c69df8d57838eb52eee78
```

The Edge1 production checkout was clean on `main`, then fast-forwarded from:

```text
e74016d89cafd3d33d0ef14a388669f16cda2877
```

to the live implementation commit before mutation.

Repository validation on Edge1 passed:

- `tests/test_control_surfaces_apache_policy.py`: 3/3 PASS;
- `tests/test_edge1_front_door_apache_policy.py`: 6/6 PASS;
- shell syntax checks for both Apache installers: PASS;
- exact redirect target assertions: PASS;
- no new `ProxyPass`, `ProxyPassReverse` or `Listen` directives in the front-door policies.

The first operator attempt stopped safely before privilege/mutation because an incorrect `python3 -m unittest tests...` invocation treated `tests` as an importable package. The corrected file-based validation passed before any production change.

## Pre-change drift gate

Immediately before mutation, the approved operator block re-verified:

- host `edge1.ww.cx`;
- clean repository at the approved implementation commit;
- expected SHA-256 hashes for `000-default.conf`, `edge1.ww.cx.conf`, and the existing Control Surfaces policy;
- expected `default.invalid` HTTP default-vhost ordering;
- expected `edge1.ww.cx` HTTPS default-vhost ordering;
- existing Control Surfaces include present;
- new default-HTTP include absent;
- Apache `Syntax OK` and active;
- chrony active.

Result: `live_drift_gate=PASS`.

## Backup and rollback

Backup created before the live files were changed:

```text
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z
```

Rollback script:

```text
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z/rollback.sh
```

The backup retains the previous default vhost, previous Control Surfaces policy, Apache vhost inventory, listener inventory and SHA-256 evidence. The rollback restores the pre-change files, removes the newly introduced default-front-door policy, runs `apache2ctl configtest`, and reloads Apache.

## Live files

Updated:

```text
/etc/apache2/wwcx-edge1-control-surfaces.conf
```

Created:

```text
/etc/apache2/wwcx-edge1-default-http-front-door.conf
```

Modified only to attach the new include:

```text
/etc/apache2/sites-available/000-default.conf
```

The named `edge1.ww.cx` vhost itself was not otherwise changed; its existing Control Surfaces include remained in place.

## Applied behavior

The new default HTTP policy matches only `/` and `/index.html` and redirects with HTTP 302 to `https://ww.cx/time/`.

The existing named Edge1 policy remains root-only and now uses the same canonical WW.CX Time target. Its FreePBX `/admin` and `/ucp` private-control access rules were not broadened.

No raw-IP HTTPS certificate workaround was introduced.

## Accepted local response matrix

Post-change host-side validation returned:

| Request | Accepted result |
| --- | --- |
| raw IPv4 HTTP `/` | `302 -> https://ww.cx/time/` |
| unmatched Host HTTP `/` | `302 -> https://ww.cx/time/` |
| `edge1.ww.cx` HTTP `/` | `301 -> https://edge1.ww.cx/` |
| `edge1.ww.cx` HTTPS `/` | `302 -> https://ww.cx/time/` |
| `edge1.ww.cx` HTTPS `/index.html` | `302 -> https://ww.cx/time/` |
| `/edge1-status/` | `200` |
| `/edge1-ops/` | `404` |
| `/api/operations/` root probe | `404` |
| authenticated private-source `/admin/` | `302 -> https://edge1.ww.cx/admin/config.php` |
| authenticated private-source `/ucp/` | `200` |
| synthetic ACME HTTP probe | `404` |
| unknown HTTPS path | `404` |
| raw HTTPS default-vhost HTTP behavior after TLS | `200` |
| `pbx.ww.cx` root | `302 -> https://pbx.ww.cx/admin/` |
| `sip.ww.cx` root | `200` |

The preserved routes matched their captured pre-change behavior.

## Apache and service acceptance

- pre-change `apache2ctl configtest`: PASS;
- post-write `apache2ctl configtest`: PASS;
- controlled Apache reload: PASS;
- post-reload `apache2ctl configtest`: PASS;
- Apache active: PASS;
- chrony active: PASS;
- TCP 80 and 443 remained Apache listeners;
- UDP 123 and TCP 4460 remained chronyd listeners;
- expected HTTP and HTTPS default-vhost ordering remained unchanged;
- no new proxy or listener directive was introduced by the new policies.

The operator block ended with:

```text
EDGE1_FRONT_DOOR_LOCAL_ACCEPTANCE=PASS
```

## Browser / outside-in verification

A connected-browser navigation to the bare root initially displayed the previously cached Debian default page. A cache-busted request demonstrated that this was stale browser content rather than current Apache behavior.

Cache-busted browser verification established:

- `https://edge1.ww.cx/?wwcx_frontdoor=20260819T0529Z` landed on `https://ww.cx/time/?wwcx_frontdoor=20260819T0529Z` with the WW.CX Time page;
- `https://edge1.ww.cx/index.html?wwcx_frontdoor=20260819T0529Z` landed on the WW.CX Time page;
- `http://89.147.109.253/?wwcx_frontdoor=20260819T0529Z` landed on the WW.CX Time page;
- `https://edge1.ww.cx/edge1-status/?wwcx_frontdoor=20260819T0529Z` continued to render the WW.CX Edge1 Operations Center;
- `https://edge1.ww.cx/__wwcx_front_door_probe__?wwcx_frontdoor=20260819T0529Z` rendered `404 Not Found` and was not consumed by the front-door redirect.

The connected browser is part of the approved private management environment and therefore is not an independent public-WAN test of `/admin/` or `/ucp/` denial. This cutover did not broaden those access rules and did not add a listener or proxy path.

An attempted independent fetch through the general web retrieval path timed out / could not resolve the direct Edge1 requests, so it is not counted as acceptance evidence.

## Security boundary outcome

This cutover did not:

- expose the localhost Time Authority dashboard;
- proxy arbitrary or internal paths;
- alter `/api/operations/`, timekeeping MCP, Electrum Watch or other explicit parent-vhost routes;
- change DNS;
- change firewall rules;
- issue or replace certificates;
- add a listener;
- change NTP, NTS or host clock synchronization;
- change Asterisk, Kamailio, carrier routing or telephony behavior;
- weaken authentication;
- delete operational data.

## Final disposition

The Edge1 public front door is accepted live at HTTP 302.

Promotion to HTTP 308 is intentionally deferred. It is a separate future change and must be evaluated only after sufficient operational experience; no automatic promotion is authorized by this acceptance.
