# Outbound Mail Phase B2 Apache Live Acceptance

Last reconciled: 2026-08-01 22:10 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Parent activation issue: #187  
Parameter and activation issue: #233

## Accepted live activation

The bounded Apache activation was executed through authenticated SSH by `wwadmin`; the activation wrapper ran as `root` through `sudo` on `edge1.ww.cx`.

Accepted facts:

- captured at: `2026-08-01T22:10:05Z`;
- deployed repository HEAD: `9bfc9d0c494da11a4fb47fe38e7390f0b12d1444`;
- approved activation commit: `d35fda6a3adcac2782ed6e8ed44ea8650a4d9df2`;
- accepted proposal evidence: `/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-apache-proposal/20260801T210934Z`;
- activation evidence: `/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-apache-activation/20260801T221005Z`;
- exact hostname: `edge1.ww.cx`;
- exact approved source: `162.0.217.71/32`;
- installed fragment: `/etc/apache2/wwcx-outbound-mail-preparation-api.conf`;
- active vhost: `/etc/apache2/sites-enabled/edge1.ww.cx.conf`;
- active vhost target: `/etc/apache2/sites-available/edge1.ww.cx.conf`;
- one include line was added inside the existing TLS virtual host;
- Apache configuration test: `Syntax OK`;
- Apache and the outbound-mail gateway remained active and enabled;
- the gateway listener remained exactly `127.0.0.1:8104`;
- no external listener was added on port 8104;
- evidence manifest verification passed;
- activation summary validation passed;
- failures: `0`.

## Access-boundary results

From an unapproved local source through the TLS virtual host:

- preparation status: HTTP `403`;
- preparation request: HTTP `403`;
- send route: HTTP `404`;
- health route: HTTP `404`.

Directly on the loopback gateway:

- health: HTTP `200`;
- unsigned preparation status: HTTP `401`;
- send: HTTP `403`.

The gateway runtime remained in the accepted no-send state:

- state: `disabled`;
- preparation API enabled: yes;
- runtime HMAC credential configured: yes;
- external delivery enabled: no;
- policy enabled: no;
- live sender count: `0`;
- ready provider count: `0`.

## Mutation and secrecy boundaries

- certificate private key exposed: no;
- HMAC secret read or disclosed: no;
- certificate generated: no;
- DNS modified: no;
- firewall modified: no;
- new public listener added: no;
- website bridge enabled: no;
- provider or sender enabled: no;
- external delivery enabled: no;
- message sent: no.

The installed Apache route is preparation-only. It exposes exactly the approved status and prepare paths to the measured business159 source. It does not expose a send route or a wildcard preparation route.

## Current state

`readiness_state=awaiting_business159_source_acceptance`

The route is installed and source-restricted, but the approved external source has not yet performed its unsigned canary. Phase B2 is not externally accepted until business159 observes:

- HTTP `401` from `GET /outbound-mail/api/v1/status`;
- HTTP `401` from an unsigned `POST /outbound-mail/api/v1/prepare`;
- HTTP `404` from `POST /outbound-mail/send`;
- HTTP `404` from `GET /outbound-mail/healthz`;
- no redirect and valid TLS verification.

No credential is required for this source-acceptance canary. Secure bridge credential installation and website bridge activation remain later, separately evidenced steps. Production delivery and an actual message remain disabled and undefined.
