# Outbound Mail Phase B2 Readiness State

Last reconciled: 2026-08-01 19:10 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative issue: #217  
Parent activation issue: #187

## Verified prerequisite

Phase B1 is accepted live on `edge1.ww.cx`:

- service `wwcx-outbound-mail-gateway.service` is active and enabled;
- service principal is `wwcx-mail-gateway`;
- listener is exactly `127.0.0.1:8104`;
- preparation authentication is enabled with a root-owned runtime credential;
- unsigned preparation requests return HTTP `401`;
- send returns HTTP `403`;
- external delivery and policy remain disabled;
- live sender count is zero;
- ready provider count is zero;
- accepted evidence is `/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1/20260801T190027Z`;
- accepted repository record merged as `53bb0ea15cdedb136add858841813273252cc8fc`.

## Current B2 work

A read-only Phase B2 readiness package is being prepared. Its purpose is to inventory and validate prerequisites without installing or exposing the TLS reverse proxy.

Package files:

- `tools/messaging/outbound_mail_phase_b2_readiness_audit.sh`;
- `docs/messaging-operations/outbound-mail-phase-b2-readiness-audit-20260801.md`;
- `tests/validate_outbound_mail_phase_b2_readiness_audit.py`.

The audit supports:

- baseline inventory with no proposal values;
- proposal validation only when all exact hostname, single-source CIDR, certificate full-chain path, and certificate private-key path values are supplied;
- restricted evidence under `/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-readiness/`;
- candidate nginx rendering into evidence only.

## Current authorization state

- B2 readiness package preparation: **authorized as safe repository work**;
- B2 audit execution: **not yet executed**;
- exact B2 hostname selected: **no**;
- exact client source `/32` or `/128` selected: **no**;
- certificate paths or issuance method selected: **no**;
- reverse-proxy destination selected: **no**;
- certificate/private-key access authorized: **no**;
- proxy installation or reload authorized: **no**;
- DNS change authorized: **no**;
- firewall change authorized: **no**;
- public listener or route authorized: **no**;
- external signed canary authorized: **no**;
- website bridge authorized: **no**;
- provider, sender, or delivery activation authorized: **no**;
- production message authorized: **no**.

## Non-mutation boundary

The readiness audit must never:

- read or display the B1 HMAC secret;
- read, hash, print, or validate certificate private-key contents;
- copy a candidate configuration into `/etc`;
- install, enable, reload, restart, or reconfigure a reverse proxy;
- issue or renew a certificate;
- change DNS, firewall rules, listeners, or routes;
- enable the website bridge, retention, provider, sender, or delivery;
- send a message.

## Required explicit B2 decision

Before any live B2 change, obtain exact authorization naming:

1. hostname;
2. certificate source and paths;
3. exact client source address;
4. reverse-proxy service and target configuration path;
5. proxy reload/restart scope;
6. DNS and firewall changes, if any;
7. external canary source;
8. rollback procedure and evidence directory.

A generic `Continue` does not authorize those privileged actions.
