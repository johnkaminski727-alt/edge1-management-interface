# Outbound Mail Phase B2 Readiness State

Last reconciled: 2026-08-01 19:28 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Acceptance issue: #224  
Parent activation issue: #187

## Verified prerequisite

Phase B1 remains accepted live on `edge1.ww.cx`:

- service `wwcx-outbound-mail-gateway.service` remains on loopback `127.0.0.1:8104`;
- preparation authentication remains enabled with a root-owned runtime credential;
- unsigned preparation requests return HTTP `401`;
- send returns HTTP `403`;
- external delivery and policy remain disabled;
- live sender count remains zero;
- ready provider count remains zero.

## Accepted Phase B2 baseline audit

The read-only baseline audit was executed through authenticated SSH by `wwadmin`; the audit itself ran as `root` through `sudo`.

Accepted facts:

- audit timestamp: `2026-08-01T19:28:18Z`;
- host: `edge1.ww.cx`;
- branch: `main`;
- audited repository HEAD: `03f8a67b17b258459ee71b6a2a7a31187987506c`;
- B1 live-acceptance commit: `53bb0ea15cdedb136add858841813273252cc8fc`;
- B2 template baseline: `f1f65571902c7f377c6a7ca9c52f634973a7635a`;
- readiness state: `awaiting_explicit_b2_parameters`;
- evidence directory: `/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-readiness/20260801T192818Z`;
- proposed hostname: not supplied;
- proposed client CIDR: not supplied;
- certificate full-chain path: not supplied;
- certificate private-key path: not supplied;
- unsigned preparation API: HTTP `401`;
- send probe: HTTP `403`.

The audit completed without reading HMAC or certificate private-key contents and without changing runtime or network state.

## Pending exact B2 parameters

A later proposal-validation run requires all four values together:

1. exact lowercase non-wildcard API hostname;
2. exact single-source IPv4 `/32` or IPv6 `/128`;
3. approved certificate full-chain path;
4. approved certificate private-key path.

No value has been selected or inferred.

## Current authorization state

- B2 baseline audit execution: **accepted**;
- B2 proposal validation: **not yet parameterized**;
- certificate/private-key content access authorized: **no**;
- proxy installation or reload authorized: **no**;
- DNS change authorized: **no**;
- firewall change authorized: **no**;
- public listener or route authorized: **no**;
- external signed canary authorized: **no**;
- website bridge authorized: **no**;
- provider, sender, or delivery activation authorized: **no**;
- production message authorized: **no**.

## Verified non-mutation markers

- `hmac_secret_read=no`;
- `certificate_private_key_read=no`;
- `candidate_config_written_to_evidence_only=yes`;
- `proxy_config_installed=no`;
- `proxy_service_reloaded=no`;
- `certificate_generated=no`;
- `dns_modified=no`;
- `firewall_modified=no`;
- `public_listener_added=no`;
- `website_bridge_enabled=no`;
- `provider_or_sender_enabled=no`;
- `message_sent=no`.

## Required explicit B2 decision

Before any live B2 change, obtain exact authorization naming the hostname, certificate source and paths, client source address, reverse-proxy service and destination path, reload scope, DNS/firewall changes if any, external canary source, rollback procedure, and evidence directory.

A generic `Continue` does not authorize those privileged actions.
